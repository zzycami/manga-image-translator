#!/usr/bin/env python3
"""
测试新图片 - 使用原生 API (端口 8000)
"""

import requests
import json
import sys

# 从命令行参数获取图片路径
if len(sys.argv) > 1:
    IMAGE_PATH = sys.argv[1]
else:
    print("用法: python test_new_image.py <图片路径>")
    sys.exit(1)

OUTPUT_PATH = IMAGE_PATH.replace('.jpg', '_translated.jpg').replace('.png', '_translated.jpg')

# API 配置
API_URL = "http://127.0.0.1:8000/translate/with-form/image"

print("=" * 60)
print("测试新图片 - 原生 API")
print("=" * 60)
print()
print(f"📁 输入图片: {IMAGE_PATH}")
print(f"💾 输出图片: {OUTPUT_PATH}")
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

    print("⏳ 翻译中（包含检测 + OCR + 翻译 + 渲染），预计 20-30 秒...")
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
    print(f"💾 结果已保存: {OUTPUT_PATH}")
    print()
else:
    print("=" * 60)
    print("❌ 翻译失败")
    print("=" * 60)
    print()
    print(f"HTTP Status: {response.status_code}")
    print(f"错误: {response.text}")
