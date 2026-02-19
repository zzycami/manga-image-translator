#!/bin/bash

# 清理 result 文件夹的脚本

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
RESULT_DIR="${SCRIPT_DIR}/result"

if [ ! -d "$RESULT_DIR" ]; then
    echo "错误: result 文件夹不存在: $RESULT_DIR"
    exit 1
fi

# 计算清理前的大小
BEFORE_SIZE=$(du -sh "$RESULT_DIR" | cut -f1)
FOLDER_COUNT=$(find "$RESULT_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l)

echo "准备清理 result 文件夹"
echo "位置: $RESULT_DIR"
echo "当前大小: $BEFORE_SIZE"
echo "文件夹数量: $FOLDER_COUNT"
echo ""

# 确认操作
read -p "确定要删除所有文件夹吗？(y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "操作已取消"
    exit 0
fi

# 执行清理
echo "正在清理..."
find "$RESULT_DIR" -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} + 2>/dev/null

# 计算清理后的大小
AFTER_SIZE=$(du -sh "$RESULT_DIR" | cut -f1)
REMAINING_COUNT=$(find "$RESULT_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)

echo ""
echo "清理完成！"
echo "清理前大小: $BEFORE_SIZE"
echo "清理后大小: $AFTER_SIZE"
echo "剩余文件夹数: $REMAINING_COUNT"

