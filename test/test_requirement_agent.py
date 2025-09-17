# test/test_requirement_agent.py
import asyncio
import json
import os
import re
import sys

import pytest
import pytest_asyncio

# 将项目根目录添加到 sys.path，确保 src 模块可导入
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agentscope.formatter import DashScopeChatFormatter
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel

from src import config
from src.agents.requirement_agent import RequirementAgent


def _try_parse_json_loose(text: str):
    """尽量从文本中解析 JSON 对象（宽松提取）。"""
    text = text.strip()
    # 尝试直接解析
    try:
        return json.loads(text)
    except Exception:
        pass

    # 从首个 '{' 到最后一个 '}' 提取
    if '{' in text and '}' in text:
        s = text.find('{')
        e = text.rfind('}')
        candidate = text[s : e + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # 退化正则（匹配最外层对象，可能失败）
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return None


@pytest.mark.asyncio
async def test_requirement_agent_outputs_schema_and_flow():
    """
    验证 RequirementAgent：
    - 返回单一 JSON 对象，包含版本、状态、摘要、阶段/问题等关键字段
    - status 为 clarification_needed 或 plan_ready；对应字段满足约束
    - 使用只读工具（检索或只读命令）探索上下文
    如未配置 API Key，跳过。
    """

    if "your_" in config.DASHSCOPE_API_KEY:
        pytest.skip("未配置有效的 API 密钥，跳过 RequirementAgent 测试。")

    model = DashScopeChatModel(
        model_name=getattr(config, "get_chat_model_name", lambda _=None: config.CHAT_MODEL_NAME)(
            "RequirementAgent"
        ),
        api_key=config.DASHSCOPE_API_KEY,
        stream=False,
    )
    formatter = DashScopeChatFormatter()

    agent = RequirementAgent(model=model, formatter=formatter)

    need = (
        "请为本仓库设计一个小步可验证的实施计划：目标是在 `src/utils/` 中新增/完善工具函数，"
        "并为相关函数补充最小测试与验证策略。严格遵循你的提示词：多轮澄清、最小阶段（3-5）、"
        "结构化 JSON 单一输出与 IMPLEMENTATION_PLAN.md 的 Markdown 内容。"
    )

    res = await agent(Msg(name="user", content=need, role="user"))
    assert res is not None, "RequirementAgent 未返回消息"

    content = res.get_text_content()
    data = _try_parse_json_loose(content)
    assert isinstance(data, dict), f"输出不是 JSON 对象: {content[:200]}..."

    # 顶层字段与基本约束
    assert data.get("version"), "缺少 version"
    assert re.match(r"^\d+\.\d+$", str(data["version"]).strip()), "version 需为形如 MAJOR.MINOR"

    assert data.get("status") in {"clarification_needed", "plan_ready"}, "status 取值非法"
    assert isinstance(data.get("requirement_summary"), str) and data["requirement_summary"].strip(), "缺少 requirement_summary"

    # 分支校验 + Markdown 片段检查
    md = data.get("plan_markdown", "")
    if data["status"] == "clarification_needed":
        qs = data.get("questions") or []
        assert isinstance(qs, list) and 1 <= len(qs) <= 5, "澄清分支需给出 1-5 条问题"
        assert any(bool(q.get("blocking")) for q in qs if isinstance(q, dict)), "至少包含一条阻断性问题"
        # 允许 plan_markdown 为空或仅包含已确定部分
        assert isinstance(md, str), "clarification_needed 分支下 plan_markdown 应为字符串"
    else:  # plan_ready
        stages = data.get("stages") or []
        assert isinstance(stages, list) and 1 <= len(stages) <= 6, "plan_ready 需包含 1-6 个阶段"
        for st in stages:
            assert isinstance(st, dict), "stages 元素需为对象"
            for k in ("name", "goal", "success_criteria", "tasks", "validation"):
                assert k in st, f"阶段缺少必需字段: {k}"
        assert (
            isinstance(md, str)
            and "## Stage" in md
            and "Goal:" in md
            and "Success Criteria:" in md
            and "Tests:" in md
            and "Status: Not Started" in md
        ), "plan_markdown 不符合模板"

    # 工具使用痕迹（记忆中应包含至少一个只读工具调用）
    mem_str = str(await agent.memory.get_memory())
    assert (
        ("execute_shell_command" in mem_str)
        or ("retrieve_knowledge" in mem_str)
        or ("view_text_file" in mem_str)
    ), "未检测到只读工具使用"


@pytest.mark.asyncio
async def test_requirement_agent_merge_answers_and_progress():
    """
    第二轮：模拟人工答复 questions，要求智能体合并更新，尽力输出 plan_ready；
    若仍为 clarification_needed，应体现有效进展：
      - 不重复已回答的问题 id；
      - 或新增 assumptions/阶段，并减少阻断性问题数量。
    """

    if "your_" in config.DASHSCOPE_API_KEY:
        pytest.skip("未配置有效的 API 密钥，跳过 RequirementAgent 测试。")

    model = DashScopeChatModel(
        model_name=getattr(config, "get_chat_model_name", lambda _=None: config.CHAT_MODEL_NAME)(
            "RequirementAgent"
        ),
        api_key=config.DASHSCOPE_API_KEY,
        stream=False,
    )
    formatter = DashScopeChatFormatter()
    agent = RequirementAgent(model=model, formatter=formatter)

    # 第一次：获取问题集
    need = (
        "基于本仓库，请产出针对 `src/utils/` 工具函数的实施计划（多轮澄清→可实施），"
        "要求使用单一 JSON 输出与计划 Markdown。"
    )
    res1 = await agent(Msg(name="user", content=need, role="user"))
    assert res1 is not None
    data1 = _try_parse_json_loose(res1.get_text_content())
    assert isinstance(data1, dict)

    qs = data1.get("questions") or []
    answered_ids: list[str] = []
    answers: list[dict] = []
    for i, q in enumerate(qs):
        if not isinstance(q, dict) or not q.get("id"):
            continue
        answered_ids.append(q["id"])
        # 针对常见问题给出合理答复
        ans_text = ""
        qq = (q.get("question") or "").lower()
        if "函数" in q.get("question", "") or "function" in qq:
            ans_text = "首批函数：format_date(date_str:str)->str; retry_with_backoff(fn, retries:int)->Any; validate_email(s:str)->bool"
        elif "测试" in q.get("question", "") or "test" in qq:
            ans_text = "采用 pytest；测试目录 tests/utils/；以最小单元测试为主，先覆盖新增函数的 happy path"
        elif "规范" in q.get("question", "") or "style" in qq or "docstring" in qq:
            ans_text = "遵循 PEP8 + Google Docstring + 类型注解；不强制覆盖率目标"
        else:
            ans_text = "按保守假设处理：优先最小可行路径，缺失处以 assumptions 记录，高风险标注"
        answers.append({"id": q["id"], "answer": ans_text})

    followup = (
        "以下是对你上轮提出的澄清问题的人工答复，请合并更新：\n"
        + json.dumps({"answers": answers, "policy": "merge_answers_and_do_not_repeat"}, ensure_ascii=False)
        + "\n不要重复已回答的问题；尽量输出 plan_ready 并生成 plan_markdown。"
    )

    res2 = await agent(Msg(name="user", content=followup, role="user"))
    assert res2 is not None
    data2 = _try_parse_json_loose(res2.get_text_content())
    assert isinstance(data2, dict), "第二轮输出不是 JSON 对象"

    status2 = data2.get("status")
    assert status2 in {"clarification_needed", "plan_ready"}

    if status2 == "plan_ready":
        md = data2.get("plan_markdown", "")
        stages = data2.get("stages") or []
        assert (
            isinstance(md, str)
            and "## Stage" in md
            and "Goal:" in md
            and "Success Criteria:" in md
            and "Tests:" in md
            and "Status: Not Started" in md
        ), "plan_markdown 不符合模板"
        assert isinstance(stages, list) and len(stages) >= 1
    else:
        # 仍需澄清时，校验不重复与进展
        qs2 = data2.get("questions") or []
        ids2 = {q.get("id") for q in qs2 if isinstance(q, dict)}
        assert not (set(answered_ids) & ids2), "仍包含已回答的问题 id"
        # 至少应出现 assumptions 或新增阶段，或阻断问题减少
        improved = False
        if data2.get("assumptions"):
            improved = True
        stages2 = data2.get("stages") or []
        if isinstance(stages2, list) and len(stages2) >= 1:
            improved = True
        # 阻断问题数量减少
        def count_blocking(items):
            return sum(1 for x in items if isinstance(x, dict) and bool(x.get("blocking")))
        if qs and qs2 and count_blocking(qs2) <= count_blocking(qs):
            improved = True
        assert improved, "第二轮未体现有效进展"

