import { describe, test, expect } from 'bun:test';
import { PlanningAgent } from '../agents/planning-agent';
import { Task } from '../types';

describe('PlanningAgent', () => {
  const apiKey = process.env.OPENAI_API_KEY || 'test-key';
  const agent = new PlanningAgent(apiKey);

  test('should initialize with API key', () => {
    expect(agent).toBeDefined();
    expect(typeof agent.createExecutionPlan).toBe('function');
  });

  test('should create execution plan for tasks', async () => {
    const tasks: Task[] = [
      {
        id: 'task_1',
        description: 'Set up project',
        type: 'config-generation',
        complexity: 'low',
        estimatedHours: 1,
        dependencies: [],
        status: 'pending',
        createdAt: new Date(),
        updatedAt: new Date(),
      },
      {
        id: 'task_2',
        description: 'Create main component',
        type: 'code-generation',
        complexity: 'medium',
        estimatedHours: 2,
        dependencies: ['task_1'],
        status: 'pending',
        createdAt: new Date(),
        updatedAt: new Date(),
      },
      {
        id: 'task_3',
        description: 'Add tests',
        type: 'test-creation',
        complexity: 'low',
        estimatedHours: 1,
        dependencies: ['task_2'],
        status: 'pending',
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    ];

    const state = {
      userInput: 'Create a React app',
      tasks,
      results: [],
      errors: [],
      metadata: {},
    };

    const result = await agent.createExecutionPlan(state);
    expect(result.executionPlan).toBeDefined();
    expect(result.executionPlan.taskGroups).toBeDefined();
    expect(Array.isArray(result.executionPlan.taskGroups)).toBe(true);
    expect(result.executionPlan.totalEstimatedHours).toBe(4);
  });

  test('should identify critical path', async () => {
    const tasks: Task[] = [
      {
        id: 'task_1',
        description: 'Setup',
        type: 'config-generation',
        complexity: 'low',
        estimatedHours: 1,
        dependencies: [],
        status: 'pending',
        createdAt: new Date(),
        updatedAt: new Date(),
      },
      {
        id: 'task_2',
        description: 'Development',
        type: 'code-generation',
        complexity: 'medium',
        estimatedHours: 3,
        dependencies: ['task_1'],
        status: 'pending',
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    ];

    const state = {
      userInput: 'Create app',
      tasks,
      results: [],
      errors: [],
      metadata: {},
    };

    const result = await agent.createExecutionPlan(state);
    expect(result.executionPlan.criticalPath).toContain('task_1');
    expect(result.executionPlan.criticalPath).toContain('task_2');
  });
});