import { AutoCodingWorkflow } from './graph/workflow';
import { AutoCodingState } from './graph/state';

export { AutoCodingWorkflow } from './graph/workflow';
export { AutoCodingState } from './graph/state';

// 主入口函数
export async function createAutoCodingAgent(apiKey: string) {
  return new AutoCodingWorkflow(apiKey);
}

// CLI 使用示例
async function main() {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    console.error('❌ Please set OPENAI_API_KEY environment variable');
    process.exit(1);
  }

  const userInput = process.argv.slice(2).join(' ');
  if (!userInput) {
    console.error('❌ Please provide a user input');
    console.log('Usage: bun run src/index.ts "Create a React todo app"');
    process.exit(1);
  }

  try {
    console.log('🚀 Starting Auto-Coding Agent...');
    console.log(`📋 Processing: ${userInput}`);
    console.log('─'.repeat(50));

    const workflow = new AutoCodingWorkflow(apiKey);
    const result = await workflow.invoke(userInput);

    console.log('\n✅ Processing completed!');
    console.log(`📊 Total tasks: ${result.tasks.length}`);
    console.log(`✅ Completed: ${result.tasks.filter(t => t.status === 'completed').length}`);
    console.log(`❌ Failed: ${result.tasks.filter(t => t.status === 'failed').length}`);
    
    if (result.errors.length > 0) {
      console.log('\n⚠️  Errors:');
      result.errors.forEach(error => console.log(`  - ${error}`));
    }

    console.log('\n📋 Task Summary:');
    result.tasks.forEach((task, index) => {
      console.log(`  ${index + 1}. ${task.description} (${task.type}) - ${task.status}`);
      if (task.validation) {
        console.log(`     Quality: ${task.validation.score}/100, Passed: ${task.validation.passed}`);
      }
      if (task.validation?.issues.length > 0) {
        console.log(`     Issues: ${task.validation.issues.length}`);
      }
    });

    // 显示生成的代码
    const generatedCode = result.tasks
      .filter(t => t.type === 'code-generation' && t.output)
      .map(t => t.output.content)
      .join('\n\n');
    
    if (generatedCode) {
      console.log('\n📄 Generated Code:');
      console.log('─'.repeat(50));
      console.log(generatedCode.slice(0, 500) + '...');
    }

  } catch (error) {
    console.error('❌ Processing failed:', error);
    process.exit(1);
  }
}

// 如果直接运行
if (require.main === module) {
  main().catch(console.error);
}

// 示例使用
export async function runExample() {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error('OPENAI_API_KEY is required');
  }

  const workflow = new AutoCodingWorkflow(apiKey);
  
  // 示例1：创建简单函数
  const result1 = await workflow.invoke('创建一个TypeScript函数用于计算斐波那契数列');
  console.log('示例1完成:', {
    totalTasks: result1.tasks.length,
    completed: result1.tasks.filter(t => t.status === 'completed').length
  });

  // 示例2：创建React组件
  const result2 = await workflow.invoke('创建一个React计数器组件');
  console.log('示例2完成:', {
    totalTasks: result2.tasks.length,
    completed: result2.tasks.filter(t => t.status === 'completed').length
  });

  return { result1, result2 };
}