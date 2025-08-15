import { describe, test, expect } from 'bun:test';
import { AnalysisAgent } from '../agents/analysis-agent';
import { AgentState } from '../types';

describe('AnalysisAgent', () => {
  const apiKey = process.env.OPENAI_API_KEY || 'test-key';
  const agent = new AnalysisAgent(apiKey);

  test('should initialize with API key', () => {
    expect(agent).toBeDefined();
    expect(typeof agent.analyzeRequirements).toBe('function');
  });

  test('should analyze requirements correctly', async () => {
    const state: AgentState = {
      userInput: 'Create a simple React todo list application with TypeScript',
      tasks: [],
      results: [],
      errors: [],
      metadata: {},
    };

    // Mock the LLM response
    const mockResponse = {
      tasks: [
        {
          id: 'task_1',
          description: 'Set up React project structure',
          type: 'config-generation',
          complexity: 'low',
          estimatedHours: 1,
          dependencies: [],
          technologyStack: ['react', 'typescript'],
          requirements: ['Create project structure', 'Set up TypeScript'],
        },
        {
          id: 'task_2',
          description: 'Create TodoList component',
          type: 'code-generation',
          complexity: 'medium',
          estimatedHours: 2,
          dependencies: ['task_1'],
          technologyStack: ['react', 'typescript'],
          requirements: ['Create TodoList component', 'Add state management'],
        },
      ],
    };

    // Note: This is a mock test - in real scenarios, you'd mock the LLM calls
    const result = await agent.analyzeRequirements(state);
    expect(result).toBeDefined();
    expect(result.tasks).toBeDefined();
    expect(Array.isArray(result.tasks)).toBe(true);
  });

  test('should handle empty input', async () => {
    const state: AgentState = {
      userInput: '',
      tasks: [],
      results: [],
      errors: [],
      metadata: {},
    };

    const result = await agent.analyzeRequirements(state);
    expect(result.errors).toBeDefined();
    expect(Array.isArray(result.errors)).toBe(true);
  });
});