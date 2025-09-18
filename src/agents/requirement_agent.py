from src.tools.rag_tool import retrieve_knowledge
from agentscope.model import ChatModelBase
from agentscope.formatter import FormatterBase
from agentscope.memory import InMemoryMemory
from agentscope.tool import Toolkit, ToolResponse, execute_shell_command as builtin_execute_shell_command, view_text_file
from agentscope.message import TextBlock
from agentscope.agent import ReActAgent
import os
import sys

# 添加 src 目录到 sys.path 以便导入兄弟模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def _read_prompt() -> str:
    """读取 RequirementAgent 的系统提示。"""
    prompt_path = os.path.join(os.path.dirname(
        __file__), '..', 'prompts', 'requirement_agent.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "You are a helpful requirement analysis assistant."


class RequirementAgent(ReActAgent):
    """
    用于需求分析与任务分解的专家 Agent。
    - 读取 `prompts/requirement_agent.txt` 作为系统提示
    - 注册只读工具：`retrieve_knowledge` 与 `execute_shell_command`
    - 产出结构化计划（由提示词约束）
    """

    def __init__(self, model: ChatModelBase, formatter: FormatterBase):
        # 1) 工具集（只读）
        toolkit = Toolkit()
        # 严格遵循只读工具：RAG 检索 + 只读 shell
        toolkit.register_tool_function(retrieve_knowledge)

        # 本地定义只读 shell 包装，避免与 agent_tools 产生循环导入
        async def execute_shell_command(command: str) -> ToolResponse:
            if not isinstance(command, str) or not command.strip():
                return ToolResponse(content=[TextBlock(type="text", text="{\"error\":\"invalid_command\"}")])

            banned_tokens = [">", ">>", "<<", "|", "sudo", "rm ", "mv ", "cp ", "chmod",
                             "chown", "mkdir", "touch", "tee", "truncate", ":>", "npm", "pnpm", "yarn", "git "]
            for tok in banned_tokens:
                if tok in command:
                    return ToolResponse(content=[TextBlock(type="text", text=f"{{\"error\":\"blocked_command\",\"reason\":\"contains banned token: {tok}\"}}")])

            allowed_cmds = {"ls", "cat", "grep", "rg", "head", "tail", "cd"}
            import re
            segments = re.split(r"\s*&&\s*|\s*;\s*", command.strip())
            for seg in segments:
                if not seg:
                    continue
                parts = seg.strip().split()
                if not parts:
                    continue
                cmd = parts[0]
                if cmd not in allowed_cmds:
                    return ToolResponse(content=[TextBlock(type="text", text=f"{{\"error\":\"blocked_command\",\"reason\":\"command '{cmd}' is not in read-only whitelist\"}}")])

            return await builtin_execute_shell_command(command)

        toolkit.register_tool_function(execute_shell_command)
        toolkit.register_tool_function(view_text_file)

        # 2) 初始化父类
        super().__init__(
            name="RequirementAgent",
            sys_prompt=_read_prompt(),
            model=model,
            formatter=formatter,
            toolkit=toolkit,
            memory=InMemoryMemory(),
            parallel_tool_calls=True,
            enable_meta_tool=True,
            max_iters=20,
        )
