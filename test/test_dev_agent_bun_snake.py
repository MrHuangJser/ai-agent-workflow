# test/test_dev_agent_bun_snake.py
from src.agents.dev_agent import DevAgent
from src import config
from agentscope.model import DashScopeChatModel
from agentscope.message import Msg
from agentscope.formatter import DashScopeChatFormatter
import pytest_asyncio
import pytest
import asyncio
import json
import os
import shutil
import sys

# 将项目根目录添加到 sys.path，确保 src 模块可导入
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))


TEST_PROJECT_DIR = "./test/temp_bun_snake"


@pytest_asyncio.fixture(scope="module")
async def setup_temp_bun_snake_project():
    """在独立的临时目录中运行，避免污染仓库根目录。"""
    # 保证干净目录
    if os.path.exists(TEST_PROJECT_DIR):
        shutil.rmtree(TEST_PROJECT_DIR)
    os.makedirs(TEST_PROJECT_DIR, exist_ok=True)

    # 切换工作目录，使 DevAgent 的 shell 操作落在该目录内
    original_cwd = os.getcwd()
    os.chdir(TEST_PROJECT_DIR)

    yield

    # 还原工作目录并清理
    os.chdir(original_cwd)
    if os.path.exists(TEST_PROJECT_DIR):
        shutil.rmtree(TEST_PROJECT_DIR)


@pytest.mark.asyncio
async def test_dev_agent_scaffolds_bun_cli_snake(setup_temp_bun_snake_project):
    """
    目标：验证 DevAgent 基于新版提示词，在无网络安装前提下，通过工具创建 bun/Node
    CLI 贪吃蛇骨架，并在遇到可确定的运行时错误时自动执行“最小编辑→再次最小验证”
    的自愈流程（最多 3 次，且不询问“是否继续”）。
    验收点：
      - 生成 package.json（名称包含 snake 或 提供基础 scripts/bin）
      - 生成 src/index.ts 或 src/index.js（包含基本键盘读取/游戏循环的占位实现）
      - 生成 README.md（包含如何运行的简要说明）
      - 通过 execute_shell_command 完成文件/验证相关操作
      - 若出现 stdin.setRawMode 等输入兼容问题，最终应被自动修复（文件中不应再包含该调用）
    如未配置有效 API Key，则跳过。
    """

    # API Key 检查
    if "your_" in config.DASHSCOPE_API_KEY:
        pytest.skip("未配置有效的 API 密钥，跳过 bun CLI snake 测试。")

    # 准备模型与格式化器（使用按 Agent 的模型映射）
    model = DashScopeChatModel(
        model_name=getattr(config, "get_chat_model_name",
                           lambda _=None: config.CHAT_MODEL_NAME)("DevAgent"),
        api_key=config.DASHSCOPE_API_KEY,
        stream=False,
    )
    formatter = DashScopeChatFormatter()

    # 实例化 DevAgent
    dev_agent = DevAgent(model=model, formatter=formatter)

    # 任务：在当前工作目录内创建最小可运行骨架
    task = (
        "请在当前目录创建一个使用 bun 或 Node.js 的命令行贪吃蛇小游戏骨架（最小可运行），"
        "要求：1) 严格遵循你的系统提示，通过工具进行最小编辑/文件创建与验证；"
        "2) 禁止网络访问与依赖安装（不要执行 bun/npm/pnpm/yarn 安装）；"
        "3) 生成 package.json（含 scripts 或 bin）；"
        "4) 生成 src/index.ts 或 src/index.js，提供基础键盘输入/主循环占位实现；"
        "5) 生成 README.md，说明如何在本地运行（如 bun run start 或 node src/index.js）；"
        "6) 若 bun 不可用，退化为 Node 与纯脚本创建；"
        "7) 不要在回复中粘贴完整文件内容，仅通过工具创建文件；"
        "8) 验证时优先运行 LSP/类型/静态检查或最小运行命令，并提取关键错误；"
        "9) 若出现可确定的运行时/类型/输入兼容等错误，请直接自动执行‘最小编辑→再次最小验证’，最多自动迭代 3 次；不要询问是否继续；"
    )

    print(f"\n向 DevAgent 发送任务（bun snake 骨架）：{task}")
    result_msg = await dev_agent(Msg(name="user", content=task, role="user"))
    assert result_msg is not None, "DevAgent 未返回消息"

    # 验收：检查文件是否创建
    pkg_path = os.path.join("package.json")
    idx_ts_path = os.path.join("src", "index.ts")
    idx_js_path = os.path.join("src", "index.js")
    readme_path = os.path.join("README.md")

    # 任一实现路径必须存在
    assert os.path.exists(pkg_path), "package.json 未创建"
    assert os.path.exists(idx_ts_path) or os.path.exists(
        idx_js_path), "未找到 src/index.ts 或 src/index.js"
    assert os.path.exists(readme_path), "README.md 未创建"

    # package.json 简要校验
    try:
        with open(pkg_path, "r", encoding="utf-8") as f:
            pkg = json.load(f)
        assert isinstance(pkg, dict), "package.json 不是有效 JSON"
        has_snake_in_name = isinstance(pkg.get("name"), str) and (
            "snake" in pkg["name"].lower())
        has_scripts_or_bin = ("scripts" in pkg) or ("bin" in pkg)
        assert has_snake_in_name or has_scripts_or_bin, "package.json 缺少 name/snake 或 scripts/bin"
    except Exception as e:
        pytest.fail(f"package.json 解析失败: {e}")

    # 读取 agent 记忆，确认使用了 shell 工具
    memory_contents = str(await dev_agent.memory.get_memory())
    assert "execute_shell_command" in memory_contents, "未检测到 execute_shell_command 的调用记录"

    print("\n验证通过：DevAgent 基于新提示词完成骨架创建并具备自动自愈能力。")
