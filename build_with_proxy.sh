#!/bin/bash
# 使用代理构建Docker镜像

# 设置代理
export https_proxy=http://127.0.0.1:7890
export http_proxy=http://127.0.0.1:7890
export all_proxy=socks5://127.0.0.1:7890

echo "=== 使用代理构建镜像 ==="
echo "代理设置："
echo "  https_proxy=$https_proxy"
echo "  http_proxy=$http_proxy"
echo "  all_proxy=$all_proxy"
echo ""

cd /Users/zhouzeyong/Documents/GitHub/manga-image-translator

echo "开始构建镜像（方案1：基于官方镜像）..."
echo "预计时间：15-35分钟（首次需要下载15GB官方镜像）"
echo ""

# 构建镜像
docker build --platform linux/amd64 -f Dockerfile.fc.optimized -t manga-image-translator:fc-optimized . 2>&1 | tee /tmp/docker-build.log

echo ""
echo "构建完成！"

