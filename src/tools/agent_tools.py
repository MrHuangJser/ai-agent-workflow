from typing import Any, Dict, List, Optional
import os
import sys
import json

from agentscope.tool import ToolResponse
from agentscope.message import TextBlock, Msg
from agentscope.formatter import DashScopeChatFormatter
from agentscope.model import DashScopeChatModel

# 添加 src 目录到 sys.path 以便导入兄弟模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import config
from src.agents.requirement_agent import RequirementAgent
from src.agents.dev_agent import DevAgent


# ---- 单次完整任务中的子 Agent 实例（保持记忆） ----
_REQ_AGENT_INSTANCE: Optional[RequirementAgent] = None
_DEV_AGENT_INSTANCE: Optional[DevAgent] = None


def _ensure_requirement_agent() -> RequirementAgent:
    global _REQ_AGENT_INSTANCE
    if _REQ_AGENT_INSTANCE is None:
        model = DashScopeChatModel(
            model_name=getattr(config, "get_chat_model_name", lambda _=None: config.CHAT_MODEL_NAME)(
                "RequirementAgent"
            ),
            api_key=config.DASHSCOPE_API_KEY,
            stream=False,
        )
        formatter = DashScopeChatFormatter()
        _REQ_AGENT_INSTANCE = RequirementAgent(model=model, formatter=formatter)
    return _REQ_AGENT_INSTANCE


def _ensure_dev_agent() -> DevAgent:
    global _DEV_AGENT_INSTANCE
    if _DEV_AGENT_INSTANCE is None:
        model = DashScopeChatModel(
            model_name=getattr(config, "get_chat_model_name", lambda _=None: config.CHAT_MODEL_NAME)(
                "DevAgent"
            ),
            api_key=config.DASHSCOPE_API_KEY,
            stream=False,
        )
        formatter = DashScopeChatFormatter()
        _DEV_AGENT_INSTANCE = DevAgent(model=model, formatter=formatter)
    return _DEV_AGENT_INSTANCE


# ---- 工具实现 ----
async def requirement_analyze(requirement_doc: str) -> ToolResponse:
    """调用 RequirementAgent 进行需求分析与澄清。

    Args:
        requirement_doc: 需求说明或上轮 answers JSON。
    Returns:
        ToolResponse: content[0]['text'] 为 RequirementAgent 返回的文本（应为单一 JSON）。
    """
    # API Key 安全提示
    if "your_" in config.DASHSCOPE_API_KEY:
        return ToolResponse(content=[TextBlock(type="text", text=json.dumps({
            "error": "missing_api_key"
        }, ensure_ascii=False))])

    agent = _ensure_requirement_agent()
    msg = await agent(Msg(name="user", content=requirement_doc, role="user"))
    text = msg.get_text_content() if msg else "{}"
    return ToolResponse(content=[TextBlock(type="text", text=text)])


async def dev_run(
    stage_name: str,
    goal: str,
    tasks: List[str],
    validation: List[str],
    constraints: Dict[str, Any] | None = None,
) -> ToolResponse:
    """调用 DevAgent 执行最小编辑与最小验证的阶段任务。

    约定输出 JSON:
        {"success": bool, "stage": str, "summary": str}
    """
    if "your_" in config.DASHSCOPE_API_KEY:
        return ToolResponse(content=[TextBlock(type="text", text=json.dumps({
            "success": False,
            "stage": stage_name,
            "error": "missing_api_key",
        }, ensure_ascii=False))])

    agent = _ensure_dev_agent()
    constraints = constraints or {}
    prompt = (
        f"请基于当前仓库执行阶段任务：\n"
        f"Stage: {stage_name}\nGoal: {goal}\n"
        f"Tasks: {tasks}\nValidation: {validation}\n"
        f"Constraints: {constraints}\n"
        f"请遵循你的系统提示词：只读定位→最小编辑→最小验证→自愈（≤3），并输出简洁的执行与验证摘要。"
    )
    msg = await agent(Msg(name="user", content=prompt, role="user"))
    result_text = msg.get_text_content() if msg else ""

    # 简单成功启发：有输出视为成功；更复杂判定可后续完善
    success = bool(result_text.strip())
    summary_json = json.dumps({
        "success": success,
        "stage": stage_name,
        "summary": (result_text[:1000] if result_text else "no output"),
    }, ensure_ascii=False)
    return ToolResponse(content=[TextBlock(type="text", text=summary_json)])


async def plan_update(markdown: str, target_path: str, overwrite: bool = True) -> ToolResponse:
    """委托写入/更新实施计划文档（例如 IMPLEMENTATION_PLAN.md）。

    安全策略：仅允许写入工作区内的相对路径；禁止越界。
    """
    # 路径安全
    safe_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    abs_target = os.path.abspath(os.path.join(safe_root, target_path))
    if not abs_target.startswith(safe_root):
        return ToolResponse(content=[TextBlock(type="text", text=json.dumps({
            "success": False,
            "error": "path_outside_workspace"
        }, ensure_ascii=False))])

    os.makedirs(os.path.dirname(abs_target), exist_ok=True)
    if os.path.exists(abs_target) and not overwrite:
        return ToolResponse(content=[TextBlock(type="text", text=json.dumps({
            "success": False,
            "error": "file_exists"
        }, ensure_ascii=False))])

    with open(abs_target, 'w', encoding='utf-8') as f:
        f.write(markdown or "")

    return ToolResponse(content=[TextBlock(type="text", text=json.dumps({
        "success": True,
        "path": target_path,
        "bytes": len(markdown or ""),
    }, ensure_ascii=False))])
