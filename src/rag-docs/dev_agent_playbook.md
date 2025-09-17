### DevAgent Playbook（参考）

目的：为 DevAgent 提供可检索的技术栈线索与常用验证手段，避免在系统提示中硬编码具体工具与命令。

使用方式：作为 RAG 文档被 `retrieve_knowledge` 查询到，由 DevAgent在“发现→计划”阶段参考。不构成强制约束。

---

#### 通用原则

- 先只读定位（目录/文件/锚点）→ 最小编辑 → 最小验证 → 小步迭代。
- 优先使用项目内已有脚本/配置；选择影响小、确定性高、可回滚的方案。
- 对可局部修复的问题直接自愈；高风险或不确定先澄清。

#### 可能的技术栈线索（示例）

- Node/JS/TS：存在 `package.json`、`tsconfig.json`、`eslint/prettier` 配置。
- Python：`pyproject.toml`（ruff/black/mypy/pyright）、`requirements.txt`、`tox.ini`。
- Go：`go.mod`、`.golangci.yml`。
- Rust：`Cargo.toml`、`rust-toolchain.toml`。
- Java：`pom.xml`、`build.gradle`。
- .NET：`*.sln`、`*.csproj`、`.editorconfig`。
- C/C++：`CMakeLists.txt`、`compile_commands.json`、`.clang-tidy`、`.clang-format`。

#### 常见最小验证手段（建议优先顺序）

1. 静态/快速验证：LSP/类型检查、lint、格式检查（尽量限定在变更文件/模块）。
2. 最小运行：仅运行受影响模块的最短路径或 smoke 测试。
3. 最小测试：优先单元测试子集；必要时扩大范围。

#### 兼容性与降级思路

- 避免使用依赖 TTY/平台的脆弱 API；提供通用替代或非交互降级。
- 工具缺失或无配置：先澄清是否允许添加最小配置或使用替代方案。

#### 输出与回滚

- 输出应包含计划要点、定位证据、最小操作、验证结果、下一步。
- 写入前显示关键片段；跨文件分批执行；必要时保留备份以便回滚。
