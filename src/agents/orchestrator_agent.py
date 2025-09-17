import json
import os
import sys
from typing import Any, Dict, List, Optional

from agentscope.agent import ReActAgent
from agentscope.formatter import FormatterBase
from agentscope.memory import InMemoryMemory
from agentscope.message import ToolUseBlock
from agentscope.model import ChatModelBase
from agentscope.tool import Toolkit

# 添加 src 目录到 sys.path 以便导入兄弟模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _read_prompt() -> str:
    """读取 Orchestrator 的系统提示。"""
    prompt_path = os.path.join(os.path.dirname(
        __file__), '..', 'prompts', 'orchestrator.txt')
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
        limits: Optional[Dict[str, Any]] = None,
    ) -> None:
        toolkit = Toolkit()
        # 注册来自 tools/agent_tools.py 的工具函数（保持一次实例化的子 Agent）
        try:
            from src.tools.agent_tools import (dev_run, plan_update,
                                               requirement_analyze)
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

        self.limits = {
            "max_clarify_rounds": 3,
            "max_stage_attempts": 3,
        }
        if limits:
            self.limits.update(limits)

    # -------- 编排入口（示意） --------

    async def run_requirement_workflow(self, requirement_doc: str) -> Dict[str, Any]:
        """简化版：单次调用 RequirementAgent 并返回解析后的 JSON。

        参考 workflow_handoffs 的思路，避免复杂的循环与外部交互，
        将多轮澄清交给 RequirementAgent 自身协议处理（status/ questions）。
        """
        res = await self._tool_call("requirement_analyze", {"requirement_doc": requirement_doc})
        data = self._parse_json(res)
        return data if isinstance(data, dict) else {"error": "invalid_requirement_output", "raw": res}

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
                    summary.append({"stage": stage.get("name"),
                                   "status": "complete", "report": report})
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
        """统一的工具调用，返回文本结果（string）。

        使用 Toolkit.call_tool_function 以保证与 AgentScope 工具系统兼容。
        """
        try:
            tool_use = ToolUseBlock(
                type="tool_use",
                id=f"orch_{tool_name}",
                name=tool_name,
                input=tool_input,
            )
            gen = await self.toolkit.call_tool_function(tool_use)
            text_content = ""
            async for tool_response in gen:
                if hasattr(tool_response, 'content') and isinstance(tool_response.content, list):
                    for item in tool_response.content:
                        if isinstance(item, dict):
                            if item.get('type') == 'text':
                                text_content += item.get('text', '')
                        else:
                            if getattr(item, 'type', None) == 'text':
                                text_content += getattr(item, 'text', '')
            return text_content
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    # 简化：去除内部交互采集逻辑，澄清多轮交互交给 RequirementAgent/外层流程

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
