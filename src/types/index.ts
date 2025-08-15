import { z } from 'zod';

// 基础类型定义
export const TaskTypeSchema = z.enum([
  'code-generation',
  'file-creation',
  'dependency-install',
  'test-creation',
  'config-generation',
]);

export const TaskStatusSchema = z.enum([
  'pending',
  'in-progress',
  'completed',
  'failed',
]);

export const TaskComplexitySchema = z.enum(['low', 'medium', 'high']);

export const IssueSeveritySchema = z.enum(['error', 'warning', 'info']);

// 任务定义
export const TaskSchema = z.object({
  id: z.string(),
  description: z.string(),
  type: TaskTypeSchema,
  complexity: TaskComplexitySchema,
  estimatedHours: z.number().min(0),
  dependencies: z.array(z.string()),
  status: TaskStatusSchema,
  output: z.any().optional(),
  validation: z.any().optional(),
  createdAt: z.date(),
  updatedAt: z.date(),
});

// 验证结果
export const IssueSchema = z.object({
  severity: IssueSeveritySchema,
  message: z.string(),
  file: z.string().optional(),
  line: z.number().optional(),
});

export const ValidationResultSchema = z.object({
  score: z.number().min(0).max(100),
  passed: z.boolean(),
  issues: z.array(IssueSchema),
  suggestions: z.array(z.string()),
});

// Agent状态
export const AgentStateSchema = z.object({
  userInput: z.string(),
  tasks: z.array(TaskSchema),
  currentTask: TaskSchema.optional(),
  executionPlan: z.any().optional(),
  results: z.array(z.any()),
  errors: z.array(z.string()),
  metadata: z.record(z.any()),
});

// Agent配置
export const AgentConfigSchema = z.object({
  openaiApiKey: z.string(),
  modelName: z.string().default('gpt-4'),
  maxRetries: z.number().min(1).max(5).default(3),
  timeoutMs: z.number().min(1000).default(30000),
  logLevel: z.enum(['debug', 'info', 'warn', 'error']).default('info'),
});

// 导出类型
type TaskType = z.infer<typeof TaskTypeSchema>;
type TaskStatus = z.infer<typeof TaskStatusSchema>;
type TaskComplexity = z.infer<typeof TaskComplexitySchema>;
type IssueSeverity = z.infer<typeof IssueSeveritySchema>;
type Task = z.infer<typeof TaskSchema>;
type Issue = z.infer<typeof IssueSchema>;
type ValidationResult = z.infer<typeof ValidationResultSchema>;
type AgentState = z.infer<typeof AgentStateSchema>;
type AgentConfig = z.infer<typeof AgentConfigSchema>;

export type {
  TaskType,
  TaskStatus,
  TaskComplexity,
  IssueSeverity,
  Task,
  Issue,
  ValidationResult,
  AgentState,
  AgentConfig,
};