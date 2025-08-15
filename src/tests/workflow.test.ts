import { describe, test, expect, beforeEach } from 'bun:test';
import { AutoCodingWorkflow } from '../graph/workflow';

describe('AutoCodingWorkflow', () => {
  let workflow: AutoCodingWorkflow;
  const apiKey = process.env.OPENAI_API_KEY || 'test-key';

  beforeEach(() => {
    workflow = new AutoCodingWorkflow(apiKey);
  });

  test('should initialize correctly', () => {
    expect(workflow).toBeDefined();
    expect(typeof workflow.invoke).toBe('function');
  });

  test('should have all required nodes', () => {
    expect(workflow['nodes']).toBeDefined();
    expect(workflow['nodes'].analysis).toBeDefined();
    expect(workflow['nodes'].planning).toBeDefined();
    expect(workflow['nodes'].execution).toBeDefined();
    expect(workflow['nodes'].validation).toBeDefined();
  });

  test('should create graph correctly', () => {
    const graph = workflow['createGraph']();
    expect(graph).toBeDefined();
  });

  test('should handle empty user input', async () => {
    const result = await workflow.invoke('');
    expect(result.userInput).toBe('');
    expect(Array.isArray(result.tasks)).toBe(true);
  });

  test('should identify ready tasks correctly', () => {
    const readyTasks = workflow['shouldContinue']({
      messages: [],
      userInput: 'test',
      tasks: [
        { id: 'task1', status: 'completed', dependencies: [], description: 'Task 1', type: 'code-generation', complexity: 'low', estimatedHours: 1, createdAt: new Date(), updatedAt: new Date() },
        { id: 'task2', status: 'pending', dependencies: ['task1'], description: 'Task 2', type: 'file-creation', complexity: 'low', estimatedHours: 1, createdAt: new Date(), updatedAt: new Date() }
      ],
      executionPlan: null,
      currentTaskIndex: 0,
      results: [],
      errors: [],
      metadata: { sessionId: 'test', startTime: new Date(), totalTasks: 2, completedTasks: 1 }
    });
    
    expect(['execution', '__end__']).toContain(readyTasks);
  });

  test('should handle errors gracefully', () => {
    const shouldEnd = workflow['shouldContinue']({
      messages: [],
      userInput: 'test',
      tasks: [],
      executionPlan: null,
      currentTaskIndex: 0,
      results: [],
      errors: ['Test error'],
      metadata: { sessionId: 'test', startTime: new Date(), totalTasks: 0, completedTasks: 0 }
    });
    
    expect(shouldEnd).toBe('__end__');
  });
});

describe('PlanningNode', () => {
  const planningNode = new PlanningNode();

  test('should calculate execution order correctly', () => {
    const tasks = [
      { id: 'task1', dependencies: [], description: 'Task 1', type: 'code-generation', complexity: 'low', estimatedHours: 1, status: 'pending', createdAt: new Date(), updatedAt: new Date() },
      { id: 'task2', dependencies: ['task1'], description: 'Task 2', type: 'file-creation', complexity: 'low', estimatedHours: 1, status: 'pending', createdAt: new Date(), updatedAt: new Date() },
      { id: 'task3', dependencies: ['task2'], description: 'Task 3', type: 'test-creation', complexity: 'low', estimatedHours: 1, status: 'pending', createdAt: new Date(), updatedAt: new Date() }
    ];

    const state = {
      messages: [],
      userInput: 'test',
      tasks,
      executionPlan: null,
      currentTaskIndex: 0,
      results: [],
      errors: [],
      metadata: { sessionId: 'test', startTime: new Date(), totalTasks: 3, completedTasks: 0 }
    };

    const result = planningNode.invoke(state);
    expect(result.executionPlan).toBeDefined();
    expect(result.executionPlan.tasks).toEqual(['task1', 'task2', 'task3']);
  });

  test('should identify parallel groups', () => {
    const tasks = [
      { id: 'task1', dependencies: [], description: 'Task 1', type: 'code-generation', complexity: 'low', estimatedHours: 1, status: 'pending', createdAt: new Date(), updatedAt: new Date() },
      { id: 'task2', dependencies: [], description: 'Task 2', type: 'file-creation', complexity: 'low', estimatedHours: 1, status: 'pending', createdAt: new Date(), updatedAt: new Date() },
      { id: 'task3', dependencies: ['task1', 'task2'], description: 'Task 3', type: 'test-creation', complexity: 'low', estimatedHours: 1, status: 'pending', createdAt: new Date(), updatedAt: new Date() }
    ];

    const state = {
      messages: [],
      userInput: 'test',
      tasks,
      executionPlan: null,
      currentTaskIndex: 0,
      results: [],
      errors: [],
      metadata: { sessionId: 'test', startTime: new Date(), totalTasks: 3, completedTasks: 0 }
    };

    const result = planningNode.invoke(state);
    expect(result.executionPlan.parallelGroups).toBeDefined();
    expect(result.executionPlan.parallelGroups[0]).toContain('task1');
    expect(result.executionPlan.parallelGroups[0]).toContain('task2');
  });
});