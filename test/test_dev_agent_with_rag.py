# test/test_dev_agent_with_rag.py
import asyncio
import os
import shutil
import sys

# 将项目根目录添加到 sys.path，确保 src 模块可导入
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import pytest_asyncio
from agentscope.formatter import DashScopeChatFormatter
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel

from src import config
from src.agents.dev_agent import DevAgent
from src.tools import rag_tool


# --- 测试设置 ---

# 定义临时目录
TEST_RAG_DOCS_DIR = "./test/temp_rag_docs"
TEST_VECTOR_DB_DIR = "./test/temp_vector_db"


@pytest_asyncio.fixture(scope="module")
async def setup_and_teardown_rag():
    """Pytest fixture，用于设置和清理 RAG 测试环境。"""
    # --- Setup ---
    print("\n--- Setting up RAG test environment ---")
    # 1. 创建临时目录和 RAG 文档
    os.makedirs(TEST_RAG_DOCS_DIR, exist_ok=True)
    standard_file_path = os.path.join(TEST_RAG_DOCS_DIR, "coding_standard.md")
    with open(standard_file_path, "w", encoding='utf-8') as f:
        f.write(
            "# 编码规范\n\n所有Python函数都必须包含 Google 风格的文档字符串 (docstring)，必须包含 `Args:` 和 `Returns:` 部分。")

    # 2. 覆盖 config 中的路径以使用临时目录
    original_rag_path = config.RAG_DOCS_PATH
    original_db_path = config.VECTOR_DB_PATH
    config.RAG_DOCS_PATH = TEST_RAG_DOCS_DIR
    config.VECTOR_DB_PATH = TEST_VECTOR_DB_DIR

    # 3. 初始化向量数据库
    vector_store = await rag_tool.initialize_vector_db()
    if vector_store is None:
        pytest.skip("未配置有效的 API 密钥，跳过 RAG 初始化测试。")
    rag_tool.set_vector_store(vector_store)

    print("--- RAG test environment setup complete ---")

    yield  # 测试将在此处运行

    # --- Teardown ---
    print("\n--- Tearing down RAG test environment ---")
    # 还原 config
    config.RAG_DOCS_PATH = original_rag_path
    config.VECTOR_DB_PATH = original_db_path

    # 删除临时目录
    if os.path.exists(TEST_RAG_DOCS_DIR):
        shutil.rmtree(TEST_RAG_DOCS_DIR)
    if os.path.exists(TEST_VECTOR_DB_DIR):
        shutil.rmtree(TEST_VECTOR_DB_DIR)
    print("--- RAG test environment teardown complete ---")

# --- 测试用例 ---


@pytest.mark.asyncio
async def test_dev_agent_uses_rag_context(setup_and_teardown_rag):
    """
    测试 DevAgent 是否能够成功调用 rag_tool.retrieve_knowledge 工具，
    并根据获取到的知识（编码规范）来完成任务。
    """
    # 1. 准备模型和格式化器
    model = DashScopeChatModel(
        model_name=config.CHAT_MODEL_NAME, api_key=config.DASHSCOPE_API_KEY, stream=False)
    assert model is not None, "未配置有效的 API 密钥，无法执行测试。"

    formatter = DashScopeChatFormatter()

    # 2. 实例化 DevAgent
    dev_agent = DevAgent(model=model, formatter=formatter)

    # 3. 定义任务，明确提示 Agent 遵循规范
    task = "请创建一个名为 'add' 的 Python 函数，它接收两个参数 a 和 b，并返回它们的和。请务必遵守项目的编码规范。"

    # 4. 执行任务
    # 注意：这是一个集成测试，会真实调用 LLM API
    print(f"\n向 DevAgent 发送任务: '{task}'")
    result_msg = await dev_agent(Msg(name="user", content=task, role="user"))

    # 5. 断言结果
    assert result_msg is not None, "Agent 没有返回任何消息"
    generated_code = result_msg.get_text_content()
    print(f"DevAgent 返回的代码:\n```python\n{generated_code}\n```")

    # 检查 agent 记忆，确认它调用了 retrieve_knowledge 工具
    memory_contents = str(await dev_agent.memory.get_memory())
    assert "retrieve_knowledge" in memory_contents, "Agent 的记忆中没有找到 retrieve_knowledge 工具的调用记录"
    assert "编码规范" in memory_contents, "Agent 似乎没有查询编码规范"

    # 检查生成的代码是否符合功能和规范要求
    assert "def add(a, b):" in generated_code, "代码中未包含 'def add(a, b):'"
    assert "return a + b" in generated_code, "代码中未包含 'return a + b'"
    assert "Args:" in generated_code, "代码中未包含 Google 风格文档字符串的 'Args:' 部分"
    assert "Returns:" in generated_code, "代码中未包含 Google 风格文档字符串的 'Returns:' 部分"

    print("\n测试成功！DevAgent 成功利用 RAG 上下文完成了任务。")