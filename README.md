# Auto-Coding Agent

基于LangGraphJS的自动写代码AI Agent系统，通过多个专业化子角色的协作，实现从用户需求到代码生成的完整自动化流程。

## 🚀 快速开始

### 环境要求
- Node.js 18+ 或 Bun 1.0+
- OpenAI API Key

### 安装

```bash
# 克隆项目
git clone <repository-url>
cd auto-coding-agent

# 安装依赖
bun install

# 设置环境变量
echo "OPENAI_API_KEY=your-openai-api-key" > .env
```

### 基本使用

#### 命令行方式

```bash
# 直接运行
bun run src/index.ts "创建一个React计数器组件"

# 使用npm脚本
bun run dev "创建一个TypeScript的HTTP客户端"
```

#### 编程方式

```typescript
import { GatewayAgent } from './src';

async function main() {
  const gateway = new GatewayAgent({
    apiKey: process.env.OPENAI_API_KEY!,
    workspacePath: './output'
  });

  const result = await gateway.processRequest('创建一个Express.js的REST API，包含用户认证功能');
  
  console.log('处理结果:', {
    总任务数: result.tasks.length,
    成功完成: result.tasks.filter(t => t.status === 'completed').length,
    失败任务: result.tasks.filter(t => t.status === 'failed').length,
    错误: result.errors
  });
}

main().catch(console.error);
```

## 🏗️ 架构设计

### 系统组件

1. **Gateway Agent** - 网关节点，管理数据流和权限
2. **Analysis Agent** - 需求分析，任务拆解
3. **Planning Agent** - 任务规划，依赖管理
4. **Execution Agent** - 任务执行，代码生成
5. **Validation Agent** - 结果验证，质量检查

### 工作流程

```
用户输入 → [Gateway] → [Analysis] → [Planning] → [Execution] → [Validation] → [Gateway] → 结果
```

## 📋 使用示例

### 示例1：创建React组件

```typescript
const result = await gateway.processRequest('创建一个React Todo应用，包含添加、删除、标记完成功能');
// 生成：
// - 项目配置文件
// - React组件
// - TypeScript类型定义
// - 测试用例
```

### 示例2：创建Node.js API

```typescript
const result = await gateway.processRequest('创建一个Express.js API，支持用户注册、登录、JWT认证');
// 生成：
// - Express路由
// - 数据库模型
// - 认证中间件
// - API文档
```

### 示例3：创建CLI工具

```typescript
const result = await gateway.processRequest('创建一个命令行工具，可以压缩图片文件');
// 生成：
// - CLI框架
// - 图片处理逻辑
// - 配置文件
// - 使用说明
```

## 🔧 配置选项

### 环境变量

```bash
# 必需
OPENAI_API_KEY=your-api-key

# 可选
WORKSPACE_PATH=./workspace
LOG_LEVEL=info
MAX_RETRIES=3
TIMEOUT_MS=30000
```

### 初始化参数

```typescript
interface GatewayAgentConfig {
  apiKey: string;           // OpenAI API Key
  workspacePath?: string;   // 工作目录 (默认: './workspace')
  modelName?: string;       // 模型名称 (默认: 'gpt-4')
  maxRetries?: number;      // 最大重试次数 (默认: 3)
  timeoutMs?: number;       // 超时时间 (默认: 30000)
}
```

## 📊 输出结果

### 任务状态

每个任务包含以下信息：
- `id`: 任务唯一标识
- `description`: 任务描述
- `type`: 任务类型（代码生成、文件创建等）
- `complexity`: 复杂度等级
- `estimatedHours`: 预估工时
- `status`: 当前状态
- `validation`: 验证结果

### 验证报告

```typescript
interface ValidationResult {
  score: number;      // 质量评分 (0-100)
  passed: boolean;    // 是否通过验证
  issues: Issue[];    // 发现的问题
  suggestions: string[]; // 改进建议
}
```

## 🧪 开发指南

### 运行测试

```bash
# 运行所有测试
bun test

# 运行特定测试文件
bun test src/tests/types.test.ts

# 监听模式
bun test --watch
```

### 代码规范

```bash
# 代码检查
bun run lint

# 代码格式化
bun run format
```

### 构建项目

```bash
# 开发模式
bun run dev

# 构建生产版本
bun run build

# 运行构建结果
bun start
```

## 🔍 调试技巧

### 启用详细日志

```typescript
import { logger } from './src/utils/logger';

// 设置日志级别
logger.setLogLevel(LogLevel.DEBUG);
```

### 查看中间结果

```typescript
const gateway = new GatewayAgent({ apiKey });

// 监听状态变化
const result = await gateway.processRequest('...');
console.log('任务列表:', result.tasks);
console.log('验证结果:', result.tasks.map(t => t.validation));
```

## 🛠️ 扩展开发

### 添加新的任务类型

1. 在 `types/index.ts` 中添加新的任务类型
2. 在 `ExecutionAgent` 中实现相应的执行逻辑
3. 在 `ValidationAgent` 中添加验证规则

### 自定义验证规则

```typescript
// 添加自定义验证检查
const customCheck = {
  name: 'Custom Check',
  description: 'Custom validation rule',
  execute: async (task, state) => {
    // 实现验证逻辑
    return true;
  }
};
```

### 集成其他AI模型

```typescript
// 使用不同的AI提供商
const customAgent = new GatewayAgent({
  apiKey: 'custom-provider-key',
  modelName: 'custom-model'
});
```

## 📈 性能优化

### 并行执行

系统会自动识别可以并行执行的任务，最大化效率。

### 缓存策略

- 任务结果缓存
- 依赖关系缓存
- 代码模板缓存

### 错误恢复

- 自动重试机制
- 失败任务隔离
- 增量执行

## 🔐 安全考虑

- API密钥安全存储
- 文件系统权限控制
- 代码执行沙箱
- 敏感信息过滤

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支
3. 添加测试用例
4. 提交Pull Request

## 📄 许可证

MIT License - 详见 LICENSE 文件

## 🆘 问题反馈

- 提交Issue: GitHub Issues
- 联系支持: [your-email]