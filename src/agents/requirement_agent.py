from agentscope.tool import execute_shell_command, view_text_file, write_text_file, insert_text_file
from src.tools.rag_tool import retrieve_knowledge
from agentscope.model import ChatModelBase
from agentscope.formatter import FormatterBase
from agentscope.memory import InMemoryMemory
from agentscope.tool import Toolkit
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
        toolkit.register_tool_function(retrieve_knowledge)
        toolkit.register_tool_function(execute_shell_command)
        toolkit.register_tool_function(view_text_file)
        toolkit.register_tool_function(write_text_file)
        toolkit.register_tool_function(insert_text_file)

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
        )
