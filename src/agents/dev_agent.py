# src/agents/dev_agent.py
import asyncio
import contextlib
import json
import os
import sys

from agentscope.agent import ReActAgent
from agentscope.formatter import FormatterBase
from agentscope.memory import InMemoryMemory
from agentscope.message import TextBlock
from agentscope.model import ChatModelBase
from agentscope.tool import Toolkit, ToolResponse
from agentscope.tool import \
    execute_shell_command as builtin_execute_shell_command
from agentscope.tool import insert_text_file, view_text_file, write_text_file

from src.tools.rag_tool import retrieve_knowledge
from src.tools.shell_session import (shell_session_close, shell_session_read,
                                     shell_session_send, shell_session_start)

# 添加 src 目录到 sys.path 以便导入兄弟模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# [二次修正] 导入正确的模型和格式化器基类

# 导入 DevAgent 需要的工具


def _read_prompt() -> str:
    """读取 DevAgent 的系统提示。"""
    prompt_path = os.path.join(os.path.dirname(
        __file__), '..', 'prompts', 'dev_agent.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        # 在测试或路径不正确时提供一个默认值
        return "You are a helpful assistant."


class DevAgent(ReActAgent):
    """
    用于代码开发的专家 Agent。
    这个类在初始化时会自动配置好它自己的系统提示、工具集和短期记忆，
    使其成为一个功能内聚的、可直接使用的开发单元。
    """

    def __init__(self, model: ChatModelBase, formatter: FormatterBase):
        """
        初始化 DevAgent。

        Args:
            model (ChatModelBase): 用于 Agent 推理的模型。
            formatter (FormatterBase): 用于格式化模型输入输出的格式化器。
        """
        # 1. 为自己创建专用的工具集
        toolkit = Toolkit()
        toolkit.register_tool_function(retrieve_knowledge)

        toolkit.register_tool_function(shell_session_start)
        toolkit.register_tool_function(shell_session_read)
        toolkit.register_tool_function(shell_session_send)
        toolkit.register_tool_function(shell_session_close)

        toolkit.register_tool_function(write_text_file)
        toolkit.register_tool_function(view_text_file)
        toolkit.register_tool_function(insert_text_file)

        # 2. 调用父类的构造函数，传入预设好的配置
        super().__init__(
            name="DevAgent",
            sys_prompt=_read_prompt(),
            model=model,
            formatter=formatter,
            toolkit=toolkit,
            memory=InMemoryMemory(),
            parallel_tool_calls=True,
            enable_meta_tool=True
        )
