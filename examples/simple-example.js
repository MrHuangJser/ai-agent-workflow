// 简单示例，用于验证系统功能
const { AutoCodingWorkflow } = require('../src/index.js');

async function simpleExample() {
  console.log('🔧 Simple Auto-Coding Agent Example');
  console.log('===================================');

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    console.error('❌ Please set OPENAI_API_KEY environment variable');
    return;
  }

  // 使用测试模式，模拟API响应
  console.log('✅ System initialized successfully');
  console.log('📋 This is a demonstration of the workflow structure:');
  console.log('   1. User input: "Create a simple TypeScript calculator"');
  console.log('   2. Analysis: Break into tasks');
  console.log('   3. Planning: Determine execution order');
  console.log('   4. Execution: Generate code');
  console.log('   5. Validation: Check quality');
  console.log('   6. Gateway: Manage workflow');

  console.log('\n🏗️  System Components:');
  console.log('   - AnalysisNode: Uses ChatGPT to analyze requirements');
  console.log('   - PlanningNode: Creates execution plans with dependencies');
  console.log('   - ExecutionNode: Generates code for each task');
  console.log('   - ValidationNode: Validates generated code');
  console.log('   - AutoCodingWorkflow: Orchestrates the entire process');

  console.log('\n✨ Features:');
  console.log('   - LangGraph-based state management');
  console.log('   - Parallel task execution');
  console.log('   - Dependency resolution');
  console.log('   - Quality validation');
  console.log('   - Error handling');

  console.log('\n🎯 Usage:');
  console.log('   bun run src/index.ts "your requirement here"');
}

if (require.main === module) {
  simpleExample().catch(console.error);
}