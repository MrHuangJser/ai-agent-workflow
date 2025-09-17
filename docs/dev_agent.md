# DevAgent 架构说明

---

#### 1. 角色定位

DevAgent 是面向代码实现与修复的工作智能体，目标是在“当前仓库”内以小步增量的方式完成变更，并通过最小验证闭环确保质量与可回滚性。

- 关注点：最小编辑、最小验证、快速反馈、自愈迭代
- 不负责：全局流程编排（由 Orchestrator 负责）、跨项目/越界操作、复杂的长事务状态管理

#### 2. 运行时依赖

- Agent 基类：`agentscope.agent.ReActAgent`
- 工具（已在 `src/agents/dev_agent.py` 注册）:
  - `retrieve_knowledge`（项目内 `src/tools/rag_tool.py`）：检索 RAG 文档（编码规范/架构约定/贡献指南等）
  - `execute_shell_command`（AgentScope 内置）：目录浏览、文件读取与受限命令执行
  - `write_text_file`（AgentScope 内置）：以安全方式创建/覆盖文本文件
  - `view_text_file`（AgentScope 内置）：只读查看文本文件（支持范围）以做锚点定位
  - `insert_text_file`（AgentScope 内置）：在给定锚点/偏移处插入文本，便于最小编辑
- 提示词：`src/prompts/dev_agent.txt`（思路驱动；发现→计划→执行→验证→自愈）
- 模型配置：按 agent 选择模型（`src/config.py` 的 `get_chat_model_name("DevAgent")`）

#### 3. 核心方法论

DevAgent 严格遵循“发现→计划→执行→验证→自愈”的闭环：

1) 发现：先只读定位上下文（目录、文件、锚点），检索必要知识（编码规范、Playbook 等）
2) 计划：提出最小可行变更方案，限定范围与影响面
3) 执行：优先使用结构化文件操作工具（`view_text_file` 定位→`insert_text_file`/`write_text_file` 修改），必要时再用 `execute_shell_command`；避免整文件重写
4) 验证：优先使用静态/快速手段（LSP、类型、风格、格式检查），必要时最小运行/测试
5) 自愈：对可局部、确定性的错误直接再次最小编辑与最小验证，最多自动迭代 3 次

设计准则：

- 影响最小、确定性最高、耗时最短、可回滚
- 先验证“变更文件/受影响模块”，再扩大范围
- 高风险或不确定改动先澄清

#### 4. 安全与约束

- 工具优先级：文件操作优先使用 `view_text_file`/`insert_text_file`/`write_text_file`，减少对 shell 编辑的依赖
- 命令限制：仅使用受限/白名单命令；禁止删除性/越权/长时阻塞/网络访问等危险操作
- 变更控制：写入前需只读确认锚点；变更分批执行，每批后进行最小验证
- 平台兼容：避免使用脆弱 API（如 TTY 依赖），提供通用替代或非交互降级

#### 5. 参考知识（RAG）

- Playbook：`src/rag-docs/dev_agent_playbook.md`，收录多技术栈线索、最小验证手段、兼容/降级思路与回滚要点
- 规范类文档：`src/rag-docs/` 目录下的编码规范、架构约定等

DevAgent 在“发现/计划”阶段可以调用 `retrieve_knowledge` 检索这些文档，作为决策依据。

#### 6. 与其他 Agent 的边界

- OrchestratorAgent（强模型）：负责任务分解、总线记忆、质量把关与回滚策略
- Requirement/Test 等 Agent：可与 DevAgent 并行存在，由 Orchestrator 调度

当前实现中，DevAgent 已集成必要工具，按照提示词自治完成计划与执行；后续若引入 WorkAgent（小模型）作为专职执行者，可将 DevAgent 产出的计划转交由其执行，以进一步控费。

#### 7. 测试与验收

- 示例测试：
  - `test/test_dev_agent_with_rag.py`：验证 DevAgent 能利用 RAG 与工具完成任务
  - `test/test_dev_agent_bun_snake.py`：验证 DevAgent 在 Node/Bun 场景的最小骨架创建与运行时错误自愈能力（依赖结构化文件操作工具与受限命令）
- 验收维度：
  - 是否按小步增量完成最小变更
  - 是否优先使用最小验证并解析关键错误
  - 是否在可确定错误下自动自愈（≤3 次）
  - 是否遵守安全约束与跨平台兼容要求

#### 8. 未来演进

- 计划/执行分离：引入 WorkAgent 以进一步降低成本并增强可控性
- 指标与可观测性：收集每轮变更规模、验证耗时、错误修复次数等指标，指导提示与策略优化
