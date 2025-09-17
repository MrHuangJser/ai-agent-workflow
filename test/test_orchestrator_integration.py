import asyncio
import json
import os
import sys

# 添加项目根目录到 sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import config
from src.agents.orchestrator_agent import OrchestratorAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.model import DashScopeChatModel


async def main() -> None:
    print("启动 Orchestrator 入口...\n")

    if "your_" in config.DASHSCOPE_API_KEY:
        print("未配置 DASHSCOPE_API_KEY，请在 .env 中配置后重试。")
        return

    model = DashScopeChatModel(
        model_name=getattr(config, "get_chat_model_name", lambda _=None: config.CHAT_MODEL_NAME)(
            "OrchestratorAgent"
        ),
        api_key=config.DASHSCOPE_API_KEY,
        stream=False,
    )
    formatter = DashScopeChatFormatter()

    orchestrator = OrchestratorAgent(
        model=model,
        formatter=formatter,
        limits={"max_clarify_rounds": 2, "max_stage_attempts": 2},
    )

    requirement_doc = os.getenv(
        "ORCH_REQUIREMENT",
        """
        需求：创建一个简单的待办事项管理 Web 应用

        功能要求：
        1. 用户可以添加新的待办事项
        2. 用户可以标记待办事项为完成
        3. 用户可以删除待办事项
        4. 显示所有待办事项的列表

        非功能要求：
        - 界面简洁易用
        - 数据持久化存储
        """,
    )

    print("输入需求：\n" + requirement_doc + "\n")
    print("运行需求澄清/计划生成...\n")
    req_result = await orchestrator.run_requirement_workflow(requirement_doc)
    print("RequirementAgent 输出：")
    try:
        print(json.dumps(req_result, ensure_ascii=False, indent=2))
    except Exception:
        print(str(req_result))

    if isinstance(req_result, dict) and req_result.get("status") == "plan_ready":
        print("\n进入分阶段执行...\n")
        exec_result = await orchestrator.run_stage_execution(
            req_result,
            constraints={"timeout": 300},
        )
        print("执行结果：")
        try:
            print(json.dumps(exec_result, ensure_ascii=False, indent=2))
        except Exception:
            print(str(exec_result))
    else:
        print("\n计划尚未就绪（clarification_needed），请完善需求后重试。")


if __name__ == "__main__":
    asyncio.run(main())
