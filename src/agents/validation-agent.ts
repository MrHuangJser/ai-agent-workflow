import { ChatOpenAI } from '@langchain/openai';
import { AgentState, Task, ValidationResult, Issue } from '../types';
import { logger } from '../utils/logger';
import { readFile } from 'fs/promises';
import { join } from 'path';

const ValidationSchema = z.object({
  score: z.number().min(0).max(100),
  passed: z.boolean(),
  issues: z.array(z.object({
    severity: z.enum(['error', 'warning', 'info']),
    message: z.string(),
    file: z.string().optional(),
    line: z.number().optional(),
  })),
  suggestions: z.array(z.string()),
  checkList: z.array(z.object({
    item: z.string(),
    passed: z.boolean(),
    details: z.string().optional(),
  })),
});

interface ValidationCheck {
  name: string;
  description: string;
  execute: (task: Task, state: AgentState) => Promise<boolean>;
  getDetails?: (task: Task, state: AgentState) => Promise<string>;
}

export class ValidationAgent {
  private llm: ChatOpenAI;

  constructor(apiKey: string) {
    this.llm = new ChatOpenAI({
      openAIApiKey: apiKey,
      modelName: 'gpt-4',
      temperature: 0.1,
    });
  }

  async validateTask(state: AgentState): Promise<Partial<AgentState>> {
    const currentTask = state.currentTask;
    if (!currentTask) {
      return { errors: [...(state.errors || []), 'No current task to validate'] };
    }

    logger.info('Starting task validation', { taskId: currentTask.id, type: currentTask.type });

    try {
      const validationResult = await this.performValidation(currentTask, state);
      
      const updatedTask = {
        ...currentTask,
        validation: validationResult,
        updatedAt: new Date(),
      };

      logger.info('Task validation completed', { 
        taskId: currentTask.id, 
        score: validationResult.score,
        passed: validationResult.passed 
      });

      return {
        currentTask: updatedTask,
        metadata: {
          ...state.metadata,
          lastValidation: validationResult,
        },
      };
    } catch (error) {
      logger.error('Task validation failed', { taskId: currentTask.id, error: error.message });

      const failedTask = {
        ...currentTask,
        status: 'failed' as const,
        updatedAt: new Date(),
      };

      return {
        currentTask: failedTask,
        errors: [...(state.errors || []), `Validation failed: ${error.message}`],
      };
    }
  }

  private async performValidation(task: Task, state: AgentState): Promise<ValidationResult> {
    const checks = this.getValidationChecks(task.type);
    const checkResults = await Promise.all(
      checks.map(async (check) => ({
        name: check.name,
        passed: await check.execute(task, state),
        details: check.getDetails ? await check.getDetails(task, state) : '',
      }))
    );

    const issues: Issue[] = [];
    const suggestions: string[] = [];

    // Process check results
    checkResults.forEach((result) => {
      if (!result.passed) {
        issues.push({
          severity: 'error',
          message: `${result.name} failed: ${result.details}`,
        });
      }
    });

    // AI-based validation
    const aiValidation = await this.performAIValidation(task, state);
    issues.push(...aiValidation.issues);
    suggestions.push(...aiValidation.suggestions);

    // Calculate score
    const totalChecks = checks.length;
    const passedChecks = checkResults.filter(r => r.passed).length;
    const baseScore = Math.round((passedChecks / totalChecks) * 100);
    
    // Adjust score based on issues
    const errorCount = issues.filter(i => i.severity === 'error').length;
    const warningCount = issues.filter(i => i.severity === 'warning').length;
    const finalScore = Math.max(0, baseScore - (errorCount * 20) - (warningCount * 5));

    return {
      score: finalScore,
      passed: finalScore >= 80 && errorCount === 0,
      issues,
      suggestions,
    };
  }

  private getValidationChecks(taskType: Task['type']): ValidationCheck[] {
    const baseChecks: ValidationCheck[] = [
      {
        name: 'Output Generated',
        description: 'Task should produce output',
        execute: (task) => Promise.resolve(!!task.output),
      },
      {
        name: 'Output Format Valid',
        description: 'Output should be in expected format',
        execute: (task) => Promise.resolve(typeof task.output === 'object'),
      },
    ];

    const typeSpecificChecks: Record<Task['type'], ValidationCheck[]> = {
      'code-generation': [
        {
          name: 'Code Compilation',
          description: 'Generated code should be syntactically correct',
          execute: async (task) => {
            const output = task.output as any;
            if (!output?.content) return false;
            return this.checkTypeScriptSyntax(output.content);
          },
        },
        {
          name: 'Code Standards',
          description: 'Code should follow basic TypeScript standards',
          execute: async (task) => {
            const output = task.output as any;
            if (!output?.content) return false;
            return this.checkCodeStandards(output.content);
          },
        },
      ],
      'file-creation': [
        {
          name: 'File Exists',
          description: 'Generated file should exist',
          execute: async (task) => {
            const output = task.output as any;
            if (!output?.filePath) return false;
            try {
              await readFile(output.filePath);
              return true;
            } catch {
              return false;
            }
          },
        },
      ],
      'dependency-install': [
        {
          name: 'Dependencies Valid',
          description: 'Dependencies should be valid package names',
          execute: async (task) => {
            const output = task.output as any;
            if (!output?.dependencies) return false;
            return this.validateDependencies(output.dependencies);
          },
        },
      ],
      'test-creation': [
        {
          name: 'Test Syntax Valid',
          description: 'Test code should be syntactically correct',
          execute: async (task) => {
            const output = task.output as any;
            if (!output?.content) return false;
            return this.checkTypeScriptSyntax(output.content);
          },
        },
      ],
      'config-generation': [
        {
          name: 'Config Format Valid',
          description: 'Configuration should be valid JSON/YAML',
          execute: async (task) => {
            const output = task.output as any;
            if (!output?.content) return false;
            return this.validateConfigFormat(output.content);
          },
        },
      ],
    };

    return [...baseChecks, ...(typeSpecificChecks[taskType] || [])];
  }

  private async performAIValidation(task: Task, state: AgentState): Promise<{ issues: Issue[], suggestions: string[] }> {
    const prompt = this.buildValidationPrompt(task, state);
    const response = await this.llm.invoke(prompt);

    try {
      const result = JSON.parse(response.content as string);
      return {
        issues: result.issues || [],
        suggestions: result.suggestions || [],
      };
    } catch (error) {
      logger.warn('AI validation parsing failed', { error: error.message });
      return { issues: [], suggestions: [] };
    }
  }

  private buildValidationPrompt(task: Task, state: AgentState): string {
    return `
你是一名代码审查专家，请对以下任务的输出进行质量检查：

任务类型：${task.type}
任务描述：${task.description}
任务输出：${JSON.stringify(task.output, null, 2)}

请分析以下内容并返回JSON格式：
{
  "issues": [
    {
      "severity": "error|warning|info",
      "message": "问题描述",
      "file": "相关文件（如适用）",
      "line": 行号（如适用）
    }
  ],
  "suggestions": ["改进建议"]
}

检查标准：
1. 代码质量：语法正确性、可读性、最佳实践
2. 功能完整性：是否满足需求
3. 安全性：潜在的安全问题
4. 性能：效率考虑
5. 可维护性：代码结构清晰度

请提供具体、可操作的反馈。
`;
  }

  private async checkTypeScriptSyntax(code: string): Promise<boolean> {
    // 简化检查：检查基本的TypeScript语法元素
    const hasValidStructure = code.includes('export') || code.includes('import');
    const hasValidTypeScript = code.includes(':') || code.includes('interface') || code.includes('type');
    return hasValidStructure && hasValidTypeScript;
  }

  private async checkCodeStandards(code: string): Promise<boolean> {
    // 检查基本代码标准
    const hasComments = code.includes('//') || code.includes('/*');
    const hasProperNaming = /[a-z][a-zA-Z0-9]*/.test(code);
    const hasErrorHandling = code.includes('try') || code.includes('catch');
    
    return hasComments && hasProperNaming && hasErrorHandling;
  }

  private async validateDependencies(dependencies: Record<string, string>): Promise<boolean> {
    // 简单的依赖验证
    const validPackages = Object.keys(dependencies).every(pkg => 
      /^[a-z0-9-@/]+$/.test(pkg)
    );
    return validPackages;
  }

  private async validateConfigFormat(content: string): Promise<boolean> {
    try {
      JSON.parse(content);
      return true;
    } catch {
      try {
        // 尝试作为YAML解析（简化版）
        return content.includes(':') && content.includes('\n');
      } catch {
        return false;
      }
    }
  }
}

import { z } from 'zod';