#!/bin/bash
# 推送镜像到阿里云ACR

echo "=== 推送镜像到ACR ==="
echo ""

# 检查镜像是否存在
if ! docker images | grep -q "manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator.*fc"; then
    echo "❌ 错误：镜像未找到，请先标记镜像"
    echo "运行: docker tag manga-image-translator:fc-optimized manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc"
    exit 1
fi

echo "镜像信息："
docker images | grep "manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator.*fc"
echo ""

echo "开始推送镜像到ACR..."
echo "预计时间：20-60分钟（镜像约10GB）"
echo ""

# 推送镜像
docker push manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc

echo ""
echo "✅ 推送完成！"

