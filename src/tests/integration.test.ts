import { describe, test, expect } from 'bun:test';
import { GatewayAgent } from '../agents/gateway-agent';
import { AnalysisAgent } from '../agents/analysis-agent';
import { PlanningAgent } from '../agents/planning-agent';
import { ValidationAgent } from '../agents/validation-agent';

describe('Integration Tests', () => {
  const apiKey = process.env.OPENAI_API_KEY || 'test-key';

  describe('Agent Initialization', () => {
    test('should initialize all agents', () => {
      expect(() => new GatewayAgent({ apiKey })).not.toThrow();
      expect(() => new AnalysisAgent(apiKey)).not.toThrow();
      expect(() => new PlanningAgent(apiKey)).not.toThrow();
      expect(() => new ValidationAgent(apiKey)).not.toThrow();
    });
  });

  describe('End-to-End Flow', () => {
    test('should process simple request', async () => {
      const gateway = new GatewayAgent({ apiKey });
      
      // This is a mock test - in real scenarios, you'd mock the LLM calls
      const result = await gateway.processRequest('Create a simple TypeScript function');
      
      expect(result).toBeDefined();
      expect(result.userInput).toBe('Create a simple TypeScript function');
      expect(result.tasks).toBeDefined();
      expect(Array.isArray(result.tasks)).toBe(true);
    });

    test('should handle errors gracefully', async () => {
      const gateway = new GatewayAgent({ apiKey });
      
      // Test with invalid API key
      const invalidGateway = new GatewayAgent({ apiKey: 'invalid-key' });
      const result = await invalidGateway.processRequest('Test request');
      
      expect(result).toBeDefined();
      expect(result.errors).toBeDefined();
    });
  });

  describe('State Management', () => {
    test('should maintain state consistency', async () => {
      const gateway = new GatewayAgent({ apiKey });
      
      const initialState = {
        userInput: 'Create a React component',
        tasks: [],
        results: [],
        errors: [],
        metadata: { test: true },
      };

      const result = await gateway.processRequest(initialState.userInput);
      
      expect(result.userInput).toBe(initialState.userInput);
      expect(result.metadata).toBeDefined();
      expect(result.metadata.sessionId).toBeDefined();
    });
  });
});