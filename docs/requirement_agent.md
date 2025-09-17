# RequirementAgent 架构说明

---

#### 1. 角色定位
RequirementAgent 将用户/业务需求转化为“小步可验证的实施计划”，并与人工进行强绑定的多轮澄清（HITL）。产出物包括：
- 面向编排器可消费的单一 JSON（版本化 Schema）
- 可直接落盘的 IMPLEMENTATION_PLAN.md 的 Markdown 计划

不负责代码实现/环境变更（除非被授权写入计划文档）。

#### 2. 运行时依赖
- 基类：`agentscope.agent.ReActAgent`
- 工具（只读优先，已在 `src/agents/requirement_agent.py` 注册）：
  - `retrieve_knowledge`（`src/tools/rag_tool.py`）：检索 RAG 文档（规范、架构、Playbook 等）
  - `execute_shell_command`（内置）：只读定位与扫描（ls、cat、grep/rg、find、head/tail）
  - `view_text_file`（内置）：只读查看文件（可范围），用于锚点定位
  - `write_text_file`、`insert_text_file`（内置）：默认禁用，仅在被 Orchestrator 授权落盘计划文档时使用
- 提示词：`src/prompts/requirement_agent.txt`（内置多轮澄清协议与版本化 JSON Schema）
- 模型配置：按 agent 选择模型（`src/config.py#get_chat_model_name("RequirementAgent")`）

#### 3. 方法论与流程（发现→计划→验证策略→澄清/风险）
1) 发现：只读探索相关模块/脚本/配置（测试/构建/LSP/类型/风格），检索 RAG 规范与 Playbook；明确 scope/out_of_scope、依赖与非功能需求（性能/安全/可观察/合规等）。
2) 计划：拆分为 3–5 个阶段；每阶段包含 goal、success_criteria（可测/Gherkin）、tasks（动词短语、最小）、validation（优先已有脚本/配置）、risks（含回滚）。
3) 澄清与风险：产出“最小且高价值”的问题集（≤5，按阻断性排序），提供 fallback 假设；逐轮合并人工答复，避免重复。

设计准则：最小可验证交付；优先使用仓库现有脚本/配置；缺失时仅建议“最小补充”。结构化输出一致、可解析、可回归（版本化 Schema）。

#### 4. 输出协议（Schema v1.0）
- 顶层字段：
  - `version`（string）: 协议版本，如 "1.0"
  - `status`（enum）: `clarification_needed` | `plan_ready`
  - `requirement_summary`（string）: 1–3 句凝练陈述
  - `scope` / `out_of_scope`（string[]）: 范围与不纳入范围
  - `assumptions`（object[]）: [{text, risk_level, rollback_hint}]（plan_ready 且仍有不确定时）
  - `questions`（object[]）: [{id, question, why_needed, impact_if_unknown, fallback_assumption, blocking, priority}]（clarification_needed 时必填）
  - `dependencies`（string[]）: 内外部依赖
  - `stages`（object[]）: [{name, goal, success_criteria[], tasks[], validation[], risks[], owner_hint}]（plan_ready 必填）
  - `deliverables`（string[]）: 产出物清单
  - `plan_markdown`（string）: 遵循 IMPLEMENTATION_PLAN 模板的 Markdown（plan_ready 必填）
  - `commit_message_suggestion`（string）: 建议提交信息

联动约束：
- clarification_needed：`questions` 必须非空且至少 1 条阻断；`plan_markdown` 可为空或仅含已确定部分。
- plan_ready：`stages` 与 `plan_markdown` 必填；若仍有不确定，需以 `assumptions` 覆盖并标注风险与回滚。

#### 5. 人机协作（HITL）与编排
- Orchestrator 负责澄清循环：解析 JSON → 将 `questions` 转发给人工 → 收集 `answers` → 再次调用 RequirementAgent 合并更新。
- 终止条件：`plan_ready` 或达到最大澄清轮次（超时采用 fallback 生成 `assumptions`）。
- 要求：收到人工答复后不得重复已答问题；尽量产出 `plan_ready`，或显著减少阻断问题数量。

#### 6. 安全与约束
- 工具白名单与只读优先；禁止安装/网络/破坏性命令/长时交互。
- 写入操作仅在被授权落盘 `IMPLEMENTATION_PLAN.md` 时启用，遵循最小变更。

#### 7. 测试与验收
- 单测：`test/test_requirement_agent.py`
  - 首轮：JSON 合规、`clarification_needed/plan_ready` 分支约束、只读工具使用痕迹。
  - 二轮：模拟人工答复，验证合并更新与收敛（`plan_ready` 或有效进展：不重复已答问题/新增 assumptions 或阶段/阻断问题减少）。

#### 8. 与其他 Agent 的边界
- Orchestrator：路由、澄清循环、落盘计划、推进 DevAgent。
- DevAgent：据实施计划小步实现/验证/自愈。

#### 9. 未来演进
- 结构化文件编辑工具化（减少 shell 依赖，复用 DevAgent 的编辑工具）。
- 计划质量评审器（独立 Agent 或评审工具）。
- JSON Schema 校验器与 CI 集成，提升一致性与可回归性。
