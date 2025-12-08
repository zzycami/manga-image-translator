#!/bin/bash
# 检查Docker构建状态

echo "=== Docker构建状态检查 ==="
echo ""

# 检查官方镜像是否已下载
echo "1. 检查官方基础镜像："
if docker images | grep -q "zyddnys/manga-image-translator.*main"; then
    echo "   ✅ 官方镜像已下载"
    docker images | grep "zyddnys/manga-image-translator.*main" | head -1
else
    echo "   ⏳ 官方镜像正在下载中..."
fi

echo ""

# 检查构建的镜像
echo "2. 检查构建的镜像："
if docker images | grep -q "manga-image-translator.*fc-optimized"; then
    echo "   ✅ 构建镜像已存在"
    docker images | grep "manga-image-translator.*fc-optimized" | head -1
else
    echo "   ⏳ 构建镜像尚未完成"
fi

echo ""

# 检查构建日志
echo "3. 最近的构建日志（最后20行）："
if [ -f /tmp/docker-build.log ]; then
    tail -20 /tmp/docker-build.log
else
    echo "   ⏳ 构建日志文件尚未创建"
fi

echo ""
echo "=== 提示 ==="
echo "构建过程可能需要15-35分钟，请耐心等待"
echo "可以随时运行此脚本检查进度：./check_build_status.sh"

