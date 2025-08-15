#!/usr/bin/env node

const { GatewayAgent } = require('../dist/index.js');

async function basicExample() {
  console.log('🚀 Auto-Coding Agent Example');
  console.log('================================');

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    console.error('❌ Please set OPENAI_API_KEY environment variable');
    process.exit(1);
  }

  const gateway = new GatewayAgent({
    apiKey,
    workspacePath: './examples/output'
  });

  const requests = [
    '创建一个简单的TypeScript函数，用于计算斐波那契数列',
    '创建一个React组件用于显示用户列表',
    '创建一个Express.js路由用于用户认证'
  ];

  for (const request of requests) {
    console.log(`\n📋 Processing: ${request}`);
    console.log('─'.repeat(50));

    try {
      const result = await gateway.processRequest(request);
      
      console.log(`✅ Completed ${result.tasks.filter(t => t.status === 'completed').length} tasks`);
      console.log(`❌ Failed ${result.tasks.filter(t => t.status === 'failed').length} tasks`);
      
      if (result.errors.length > 0) {
        console.log('⚠️  Errors:', result.errors);
      }

      console.log('\n📊 Tasks:');
      result.tasks.forEach(task => {
        console.log(`  - ${task.description} (${task.type}) - ${task.status}`);
        if (task.validation) {
          console.log(`    Quality: ${task.validation.score}/100`);
        }
      });

    } catch (error) {
      console.error('❌ Error:', error.message);
    }

    console.log('\n' + '='.repeat(50));
  }
}

if (require.main === module) {
  basicExample().catch(console.error);
}