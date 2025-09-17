from agentscope.agent import ReActAgent
from agentscope.tool import Toolkit
from agentscope.model import ChatModelBase
from agentscope.formatter import FormatterBase
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
import os
import sys
import json
from typing import Callable, Optional, Any, Dict, List

# 添加 src 目录到 sys.path 以便导入兄弟模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _read_prompt() -> str:
    """读取 Orchestrator 的系统提示。"""
    prompt_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'orchestrator.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "You are an orchestrator. Coordinate agents and enforce HITL workflow."


class OrchestratorAgent(ReActAgent):
    """
    协调器智能体：
    - 读取 orchestrator 提示词
    - 注册必要工具（通过外部注入/工具模块注册）
    - 提供两个编排循环：需求澄清（HITL）与分阶段执行

    说明：
    - 实际的工具函数（如 requirement_analyze、dev_run、plan_update）由上层通过 Toolkit 注册。
    - 人工答复采用回调注入（ask_user_fn），编排器仅负责提问与合并。
    """

    def __init__(
        self,
        model: ChatModelBase,
        formatter: FormatterBase,
        *,
        ask_user_fn: Optional[Callable[[List[Dict[str, Any]]], Dict[str, Any]]] = None,
        limits: Optional[Dict[str, Any]] = None,
    ) -> None:
        toolkit = Toolkit()
        # 注册来自 tools/agent_tools.py 的工具函数（保持一次实例化的子 Agent）
        try:
            from src.tools.agent_tools import requirement_analyze, dev_run, plan_update
            toolkit.register_tool_function(requirement_analyze)
            toolkit.register_tool_function(dev_run)
            toolkit.register_tool_function(plan_update)
        except Exception:
            # 允许在未就绪时由应用侧注入
            pass

        super().__init__(
            name="OrchestratorAgent",
            sys_prompt=_read_prompt(),
            model=model,
            formatter=formatter,
            toolkit=toolkit,
            memory=InMemoryMemory(),
            parallel_tool_calls=True,
            enable_meta_tool=True,
        )

        self.ask_user_fn = ask_user_fn
        self.limits = {
            "max_clarify_rounds": 3,
            "max_stage_attempts": 3,
        }
        if limits:
            self.limits.update(limits)

    # -------- 编排入口（示意） --------
    async def run_requirement_workflow(self, requirement_doc: str) -> Dict[str, Any]:
        """运行需求澄清循环，返回 Requirement JSON（plan_ready 收敛）。"""
        rounds = 0
        current_input = requirement_doc
        last_json: Dict[str, Any] | None = None

        while rounds < self.limits["max_clarify_rounds"]:
            res = await self._tool_call("requirement_analyze", {"requirement_doc": current_input})
            data = self._parse_json(res)
            if not isinstance(data, dict) or not data.get("status"):
                return {"error": "invalid_requirement_output", "raw": res}

            status = data["status"]
            if status == "plan_ready":
                return data

            # clarification_needed
            questions = data.get("questions") or []
            if not questions:
                # 没有问题可问，尝试从 fallback 生成 assumptions，再次分析
                current_input = json.dumps({
                    "answers": [],
                    "policy": "use_fallback_assumptions",
                }, ensure_ascii=False)
                rounds += 1
                last_json = data
                continue

            # 请求人工答复（若可用），否则退化采用 fallback
            answers_payload: Dict[str, Any] = {"answers": [], "policy": "merge_answers_and_do_not_repeat"}
            if self.ask_user_fn:
                try:
                    answers_payload = self.ask_user_fn(questions) or answers_payload
                except Exception:
                    pass
            else:
                # 无人工回调，采用 fallback 假设
                for q in questions:
                    if isinstance(q, dict) and q.get("id"):
                        answers_payload["answers"].append({
                            "id": q["id"],
                            "answer": q.get("fallback_assumption", "使用保守假设推进"),
                        })

            current_input = json.dumps(answers_payload, ensure_ascii=False)
            rounds += 1
            last_json = data

        # 超轮次：强制收敛为 plan_ready（基于最后一次输出组装 assumptions）
        if last_json:
            assumptions = []
            for q in last_json.get("questions", []) or []:
                if isinstance(q, dict):
                    assumptions.append({
                        "text": q.get("fallback_assumption", "保守假设"),
                        "risk_level": "high",
                        "rollback_hint": "待获答复后修正计划",
                    })
            return {
                "version": last_json.get("version", "1.0"),
                "status": "plan_ready",
                "requirement_summary": last_json.get("requirement_summary", ""),
                "assumptions": assumptions,
                "stages": last_json.get("stages", []),
                "plan_markdown": last_json.get("plan_markdown", ""),
            }

        return {"error": "no_requirement_output"}

    async def run_stage_execution(self, requirement_json: Dict[str, Any], constraints: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """按 stages 顺序推进，调用 dev_run 执行与验证。"""
        stages = requirement_json.get("stages") or []
        summary: List[Dict[str, Any]] = []
        for stage in stages:
            if not isinstance(stage, dict):
                continue
            attempts = 0
            while attempts < self.limits["max_stage_attempts"]:
                res = await self._tool_call("dev_run", {
                    "stage_name": stage.get("name"),
                    "goal": stage.get("goal"),
                    "tasks": stage.get("tasks", []),
                    "validation": stage.get("validation", []),
                    "constraints": constraints or {},
                })
                report = self._parse_json(res)
                if isinstance(report, dict) and report.get("success"):
                    summary.append({"stage": stage.get("name"), "status": "complete", "report": report})
                    break
                attempts += 1
                if attempts >= self.limits["max_stage_attempts"]:
                    summary.append({
                        "stage": stage.get("name"),
                        "status": "failed",
                        "report": report,
                        "decision": "rollback_or_degrade",
                    })
                    # 这里仅记录决策，具体回滚/降级由外部工具执行
                    break

        return {"execution_summary": summary}

    # -------- 内部工具封装 --------
    async def _tool_call(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """统一的工具调用，返回文本结果（string）。"""
        # 通过 ReActAgent 的工具接口调用：构建 ToolUseBlock 风格输入
        # 在 agentscope 内部，会根据注册的 JSON schema 匹配工具
        msg = Msg(name=self.name, content=json.dumps({"tool": tool_name, "input": tool_input}, ensure_ascii=False), role="assistant")
        res = await self(msg)
        return res.get_text_content() if res else ""

    @staticmethod
    def _parse_json(text: str) -> Any:
        try:
            return json.loads(text)
        except Exception:
            # 宽松提取
            text = text.strip()
            if '{' in text and '}' in text:
                s = text.find('{')
                e = text.rfind('}')
                try:
                    return json.loads(text[s:e+1])
                except Exception:
                    return {"raw": text}
            return {"raw": text}


