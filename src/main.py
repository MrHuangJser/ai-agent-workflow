import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, List

# 将项目根目录加入 sys.path（便于直接运行）
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from src import config
from src.agents.orchestrator_agent import OrchestratorAgent
from src.tools.rag_tool import initialize_vector_db
from agentscope.formatter import DashScopeChatFormatter
from agentscope.model import DashScopeChatModel


def _read_requirement_from_stdin() -> str:
    print("请输入需求内容，结束后单独输入一行 .end 并回车：\n")
    lines: List[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == ".end":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _ask_answers_interactively(questions: List[Dict[str, Any]]) -> Dict[str, Any]:
    print("\n需要澄清的问题（直接回车采用保守假设；输入 ! 跳过该问题）：")
    answers: List[Dict[str, str]] = []
    for idx, q in enumerate(questions, start=1):
        if not isinstance(q, dict) or not q.get("id"):
            continue
        q_id = q.get("id")
        q_text = q.get("question", "(无问题文本)")
        fallback = q.get("fallback_assumption", "使用保守假设推进")
        try:
            user_input = input(f"  Q{idx} ({q_id}): {q_text}\n    回答(默认: {fallback}): ")
        except EOFError:
            user_input = ""
        user_input = (user_input or "").strip()
        if user_input == "!":
            continue
        answer = user_input if user_input else fallback
        answers.append({"id": q_id, "answer": answer})

    return {"answers": answers, "policy": "merge_answers_and_do_not_repeat"}


async def main() -> None:
    parser = argparse.ArgumentParser(description="Orchestrator CLI 入口")
    parser.add_argument("-r", "--requirement", type=str, help="直接传入需求文本")
    parser.add_argument("-f", "--file", type=str, help="从文件读取需求文本")
    parser.add_argument("--no-exec", action="store_true", help="只生成计划，不执行阶段任务")
    parser.add_argument("--rounds", type=int, default=5, help="最大澄清轮次，默认 5")
    parser.add_argument("--no-rag", action="store_true", help="不初始化向量数据库")
    args = parser.parse_args()

    if "your_" in config.DASHSCOPE_API_KEY:
        print("未配置 DASHSCOPE_API_KEY，请在 .env 中配置后重试。")
        return

    # 读取需求
    requirement_doc = (
        args.requirement
        or (open(args.file, "r", encoding="utf-8").read() if args.file else None)
        or os.getenv("ORCH_REQUIREMENT")
        or _read_requirement_from_stdin()
    )
    requirement_doc = (requirement_doc or "").strip()
    if not requirement_doc:
        print("未提供需求内容。退出。")
        return

    # 初始化模型与编排器
    model = DashScopeChatModel(
        model_name=getattr(config, "get_chat_model_name", lambda _=None: config.CHAT_MODEL_NAME)(
            "OrchestratorAgent"
        ),
        api_key=config.DASHSCOPE_API_KEY,
        stream=False,
    )
    formatter = DashScopeChatFormatter()
    orchestrator = OrchestratorAgent(model=model, formatter=formatter)

    # 初始化向量数据库（供 RequirementAgent 使用）
    if not args.no_rag:
        try:
            await initialize_vector_db(agent_name="RequirementAgent")
        except Exception as e:
            print(f"初始化向量数据库失败：{e}")

    # 多轮：需求 →（clarification_needed -> 人工回答）→ 收敛 plan_ready
    current_input = requirement_doc
    for round_idx in range(args.rounds):
        print(f"\n=== 需求分析 Round {round_idx + 1} ===")
        res = await orchestrator.run_requirement_workflow(current_input)
        try:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        except Exception:
            print(str(res))

        if not isinstance(res, dict):
            print("结果格式异常，退出。")
            return

        status = res.get("status")
        if status == "plan_ready":
            print("\n计划已就绪。")
            if args.no_exec:
                return
            print("\n=== 执行阶段任务 ===")
            exec_report = await orchestrator.run_stage_execution(res, constraints={"timeout": 300})
            try:
                print(json.dumps(exec_report, ensure_ascii=False, indent=2))
            except Exception:
                print(str(exec_report))
            return

        if status == "clarification_needed":
            questions = res.get("questions") or []
            if not questions:
                print("无澄清问题但未收敛，退出。")
                return
            answers_payload = _ask_answers_interactively(questions)
            current_input = json.dumps(answers_payload, ensure_ascii=False)
            continue

        print("状态未知或未包含 status 字段，退出。")
        return

    print("达到最大澄清轮次，退出。")


if __name__ == "__main__":
    asyncio.run(main())


