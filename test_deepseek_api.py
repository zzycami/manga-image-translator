#!/usr/bin/env python3
"""
测试DeepSeek API是否正常工作
"""
import os
import sys
import asyncio
from manga_translator.translators.deepseek import DeepseekTranslator

async def test_deepseek():
    """测试DeepSeek API"""
    api_key = os.getenv('DEEPSEEK_API_KEY', 'sk-fa51105a356949fa91dc262b7eea2aa6')
    
    if not api_key:
        print("❌ 错误: 未找到DEEPSEEK_API_KEY环境变量")
        return False
    
    print(f"🔑 使用API Key: {api_key[:10]}...")
    print("🧪 正在测试DeepSeek API...")
    
    translator = DeepseekTranslator()
    
    # 测试翻译
    test_text = ["こんにちは", "これはテストです"]
    try:
        result = await translator.translate('JPN', 'CHS', test_text, False)
        print(f"✅ API测试成功！")
        print(f"📝 原文: {test_text}")
        print(f"📝 译文: {result}")
        return True
    except Exception as e:
        print(f"❌ API测试失败: {e}")
        if "402" in str(e) or "Insufficient Balance" in str(e):
            print("💡 提示: 账户余额不足，请充值后重试")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_deepseek())
    sys.exit(0 if result else 1)


