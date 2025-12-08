#!/bin/bash
# 简单的测试脚本 - 翻译任意图片
# 用法: ./test_image_simple.sh <图片路径>

if [ -z "$1" ]; then
    echo "用法: ./test_image_simple.sh <图片路径>"
    echo "例如: ./test_image_simple.sh /Users/zhouzeyong/Downloads/test.jpg"
    exit 1
fi

INPUT_IMAGE="$1"
OUTPUT_IMAGE="${INPUT_IMAGE%.*}_result.jpg"

echo "======================================"
echo "输入图片: $INPUT_IMAGE"
echo "输出图片: $OUTPUT_IMAGE"
echo "======================================"
echo ""
echo "开始翻译..."
echo ""

cd /Users/zhouzeyong/Documents/GitHub/manga-image-translator
source venv/bin/activate
export DEEPSEEK_API_KEY="sk-fa51105a356949fa91dc262b7eea2aa6"

python3 << EOF
import requests
import json

IMAGE_PATH = "$INPUT_IMAGE"
OUTPUT_PATH = "$OUTPUT_IMAGE"
API_URL = "http://127.0.0.1:8000/translate/with-form/image"

config = {
    "translator": {"translator": "deepseek", "target_lang": "CHS"},
    "detector": {"detector": "default"},
    "inpainter": {"inpainter": "lama_large"},
    "ocr": {},
    "render": {}
}

with open(IMAGE_PATH, 'rb') as f:
    files = {'image': ('test.jpg', f, 'image/jpeg')}
    data = {'config': json.dumps(config)}
    response = requests.post(API_URL, files=files, data=data, timeout=300)

if response.status_code == 200:
    with open(OUTPUT_PATH, 'wb') as out:
        out.write(response.content)
    print(f"✅ 翻译成功！")
    print(f"💾 结果已保存: {OUTPUT_PATH}")
else:
    print(f"❌ 翻译失败: {response.status_code}")
    print(response.text)
EOF
