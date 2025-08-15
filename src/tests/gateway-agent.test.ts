import { describe, test, expect } from 'bun:test';
import { GatewayAgent } from '../agents/gateway-agent';

describe('GatewayAgent', () => {
  const apiKey = process.env.OPENAI_API_KEY || 'test-key';
  const gateway = new GatewayAgent({ apiKey });

  test('should initialize with API key', () => {
    expect(gateway).toBeDefined();
    expect(typeof gateway.processRequest).toBe('function');
  });

  test('should build graph correctly', () => {
    expect(gateway['graph']).toBeDefined();
    expect(gateway['graph'].channels).toBeDefined();
  });

  test('should handle empty user input gracefully', async () => {
    const result = await gateway.processRequest('');
    expect(result.errors).toBeDefined();
    expect(Array.isArray(result.errors)).toBe(true);
  });

  test('should find ready tasks correctly', () => {
    const readyTasks = gateway['findReadyTasks'](
      [
        { id: 'task_2', dependencies: ['task_1'], status: 'pending' },
        { id: 'task_3', dependencies: ['task_1'], status: 'pending' },
      ],
      [
        { id: 'task_1', dependencies: [], status: 'completed' },
        { id: 'task_2', dependencies: ['task_1'], status: 'pending' },
        { id: 'task_3', dependencies: ['task_1'], status: 'pending' },
      ]
    );
    
    expect(readyTasks).toHaveLength(2);
    expect(readyTasks.map(t => t.id)).toContain('task_2');
    expect(readyTasks.map(t => t.id)).toContain('task_3');
  });

  test('should determine continuation correctly', () => {
    const stateWithErrors = {
      userInput: 'test',
      tasks: [],
      results: [],
      errors: ['Test error'],
      metadata: {},
    };

    const stateCompleted = {
      userInput: 'test',
      tasks: [],
      results: [],
      errors: [],
      metadata: { allTasksCompleted: true },
    };

    const shouldContinue = gateway['shouldContinue'];
    
    expect(shouldContinue(stateWithErrors)).toBe('__end__');
    expect(shouldContinue(stateCompleted)).toBe('__end__');
  });
});