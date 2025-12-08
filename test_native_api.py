#!/usr/bin/env python3
"""
测试 manga-translator 原生 API (端口 8001)
验证完整翻译功能是否正常工作
"""

import requests
import json

# 测试图片路径
IMAGE_PATH = "/Users/zhouzeyong/Documents/GitHub/pixivlite-server/app/src/main/resources/static/test.jpg"
OUTPUT_PATH = "/Users/zhouzeyong/Documents/GitHub/pixivlite-server/app/src/main/resources/static/manga_native_api_result.jpg"

# API 配置
API_URL = "http://127.0.0.1:8000/translate/with-form/image"

print("=" * 60)
print("测试 manga-translator 原生 API")
print("=" * 60)
print()
print("📤 上传图片并请求翻译...")
print()

# 构建 Config JSON
config = {
    "translator": {
        "translator": "deepseek",
        "target_lang": "CHS"
    },
    "detector": {
        "detector": "default"
    },
    "inpainter": {
        "inpainter": "lama_large"
    },
    "ocr": {},
    "render": {}
}

# 发送请求
with open(IMAGE_PATH, 'rb') as f:
    files = {'image': ('test.jpg', f, 'image/jpeg')}
    data = {'config': json.dumps(config)}

    print(f"配置: {json.dumps(config, indent=2, ensure_ascii=False)}")
    print()
    print("⏳ 处理中，预计需要 20-30 秒...")
    print()

    response = requests.post(API_URL, files=files, data=data, timeout=300)

if response.status_code == 200:
    # 保存结果
    with open(OUTPUT_PATH, 'wb') as out_file:
        out_file.write(response.content)

    print("=" * 60)
    print("✅ 翻译成功！")
    print("=" * 60)
    print()
    print(f"💾 结果已保存到: {OUTPUT_PATH}")
    print()
    print("🎉 测试成功！原生 API 翻译功能正常工作！")
    print()
    print("=" * 60)
else:
    print("=" * 60)
    print("❌ 翻译失败")
    print("=" * 60)
    print()
    print(f"HTTP Status: {response.status_code}")
    print(f"错误信息: {response.text}")
    print()
    print("=" * 60)
