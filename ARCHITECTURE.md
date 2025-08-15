# Auto-Coding Agent 架构文档

## 🎯 项目概述

这是一个基于 **LangGraph** 的自动写代码AI Agent系统，通过5个专业Agent的协作，实现从用户需求到代码生成的完整自动化流程。

## 🏗️ 架构设计

### 核心架构

```
用户输入 → AnalysisNode → PlanningNode → GatewayNode → ExecutionNode → ValidationNode → 结果输出
```

### 系统组件

#### 1. AnalysisNode（需求分析节点）
- **功能**: 将用户需求分解为可执行的技术任务
- **输入**: 用户自然语言需求
- **输出**: 结构化任务列表
- **技术栈**: ChatOpenAI (GPT-4)

#### 2. PlanningNode（任务规划节点）
- **功能**: 分析任务依赖关系，制定执行计划
- **输入**: 任务列表
- **输出**: 执行计划、并行分组、关键路径
- **算法**: 拓扑排序 + 关键路径分析

#### 3. ExecutionNode（任务执行节点）
- **功能**: 执行具体的代码生成任务
- **输入**: 单个任务描述
- **输出**: 生成的代码/文件内容
- **支持类型**: 代码生成、文件创建、依赖安装、测试创建、配置生成

#### 4. ValidationNode（任务验证节点）
- **功能**: 对生成结果进行质量检查
- **输入**: 任务输出
- **输出**: 验证报告（评分、问题、建议）

#### 5. GatewayNode（网关节点）
- **功能**: 管理整个工作流的状态和任务调度
- **核心功能**: 
  - 任务状态管理
  - 依赖关系检查
  - 并行任务识别
  - 错误处理

## 📊 数据流

### 状态管理 (AutoCodingState)

```typescript
interface AutoCodingState {
  messages: BaseMessage[];        // 对话历史
  userInput: string;             // 用户输入
  tasks: Task[];                 // 任务列表
  executionPlan: any;            // 执行计划
  currentTaskIndex: number;      // 当前任务索引
  results: TaskResult[];         // 执行结果
  errors: string[];             // 错误信息
  metadata: {                   // 元数据
    sessionId: string;
    startTime: Date;
    endTime?: Date;
    totalTasks: number;
    completedTasks: number;
  };
}
```

### 任务结构 (Task)

```typescript
interface Task {
  id: string;                    // 唯一标识
  description: string;           // 任务描述
  type: TaskType;               // 任务类型
  complexity: 'low' | 'medium' | 'high';
  estimatedHours: number;       // 预估工时
  dependencies: string[];       // 依赖任务ID
  status: TaskStatus;           // 当前状态
  output?: any;                // 任务输出
  validation?: ValidationResult; // 验证结果
}
```

## 🔄 LangGraph 集成

### 状态图设计

```typescript
const workflow = new StateGraph({
  channels: {
    messages: { /* 消息累积 */ },
    userInput: { /* 用户输入 */ },
    tasks: { /* 任务列表 */ },
    executionPlan: { /* 执行计划 */ },
    currentTaskIndex: { /* 任务索引 */ },
    results: { /* 执行结果 */ },
    errors: { /* 错误信息 */ },
    metadata: { /* 元数据 */ }
  }
});
```

### 工作流节点

1. **START** → **analysis** → **planning** → **gateway** → **execution** → **validation** → **gateway** → **END**

2. **条件路由**: Gateway节点根据任务状态决定继续执行或结束

## 🚀 使用示例

### 基本使用

```typescript
import { AutoCodingWorkflow } from './graph/workflow';

const workflow = new AutoCodingWorkflow(process.env.OPENAI_API_KEY);
const result = await workflow.invoke('创建一个React计数器组件');
```

### 完整示例

```bash
# 安装依赖
bun install

# 设置API密钥
echo "OPENAI_API_KEY=your-key" > .env

# 运行示例
bun run src/index.ts "创建一个TypeScript的HTTP客户端"
```

## 📁 项目结构

```
src/
├── graph/
│   ├── state.ts           # 状态定义
│   ├── nodes.ts           # 各个节点实现
│   └── workflow.ts        # 主工作流
├── utils/
│   ├── logger.ts          # 日志工具
│   └── id-generator.ts    # ID生成器
├── tests/
│   ├── workflow.test.ts   # 工作流测试
│   └── *.test.ts         # 其他测试
├── examples/
│   ├── simple-example.js  # 简单示例
│   └── basic-usage.js     # 使用示例
├── index.ts              # 主入口
└── types/                # 类型定义
```

## ⚡ 核心特性

### 1. 智能任务分解
- 自动识别技术需求
- 合理估算工作量
- 准确识别依赖关系

### 2. 并行执行优化
- 自动识别可并行任务
- 关键路径分析
- 风险因子识别

### 3. 质量保证
- 代码质量验证
- 最佳实践检查
- 安全性检查

### 4. 错误处理
- 失败任务隔离
- 错误信息详细记录
- 优雅降级处理

## 🎯 支持的开发场景

### 代码生成
- TypeScript/JavaScript函数
- React组件
- Express.js API
- CLI工具

### 文件创建
- README文档
- 配置文件
- 测试用例
- 项目模板

### 依赖管理
- package.json生成
- 依赖版本管理
- 开发依赖识别

## 🔧 配置选项

### 环境变量

```bash
OPENAI_API_KEY=your-api-key    # 必需
WORKSPACE_PATH=./workspace     # 可选
LOG_LEVEL=info                # 可选
MODEL_NAME=gpt-4             # 可选
MAX_RETRIES=3               # 可选
TIMEOUT_MS=30000            # 可选
```

### 初始化参数

```typescript
const workflow = new AutoCodingWorkflow(apiKey, {
  modelName: 'gpt-4',
  temperature: 0.1,
  maxRetries: 3,
  timeoutMs: 30000
});
```

## 📊 性能指标

- **任务分解准确率**: 基于GPT-4的自然语言理解
- **并行执行效率**: 自动识别并行任务，提高执行效率
- **质量评分**: 0-100分的代码质量评估
- **错误恢复**: 失败任务不影响其他任务执行

## 🧪 测试覆盖

- ✅ 单元测试: 各节点独立测试
- ✅ 集成测试: 完整工作流测试
- ✅ 边界测试: 异常输入处理
- ✅ 性能测试: 大型项目处理

## 🚀 扩展开发

### 添加新任务类型

1. 在TaskType中添加新类型
2. 在ExecutionNode中添加处理逻辑
3. 在ValidationNode中添加验证规则

### 集成其他AI模型

```typescript
// 支持Anthropic Claude
const workflow = new AutoCodingWorkflow({
  provider: 'anthropic',
  modelName: 'claude-3-sonnet'
});
```

### 自定义验证规则

```typescript
class CustomValidationNode extends ValidationNode {
  protected buildValidationPrompt(task: Task): string {
    return `Custom validation logic for: ${task.type}`;
  }
}
```

## 📈 未来扩展

- [ ] 支持更多编程语言
- [ ] 集成代码仓库操作
- [ ] 添加代码审查功能
- [ ] 支持项目模板
- [ ] 添加性能优化建议
- [ ] 支持多模态输入（图片、图表等）

## 📝 总结

这个Auto-Coding Agent系统充分利用了LangGraph的状态管理和节点编排能力，实现了：

1. **专业的AI协作**: 5个专业Agent各司其职
2. **智能的任务调度**: 自动识别并行执行机会
3. **完整的质量保证**: 从需求到验证的闭环
4. **灵活的扩展性**: 基于LangGraph的架构设计
5. **生产就绪**: 完整的错误处理和监控

系统现在完全满足需求，可以直接用于生产环境！