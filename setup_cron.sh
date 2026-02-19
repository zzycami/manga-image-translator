#!/bin/bash

# 设置定时清理任务的脚本

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CLEANUP_SCRIPT="${SCRIPT_DIR}/cleanup_result_cron.sh"
LOG_FILE="/root/manga-translator/cleanup_result.log"

# 确保脚本有执行权限
chmod +x "$CLEANUP_SCRIPT"

# 创建日志文件（如果不存在）
touch "$LOG_FILE"

echo "正在设置定时清理任务..."
echo "清理脚本: $CLEANUP_SCRIPT"
echo "执行时间: 每天凌晨 4:00"
echo ""

# 检查是否已经存在相同的 cron 任务
if crontab -l 2>/dev/null | grep -q "$CLEANUP_SCRIPT"; then
    echo "⚠️  定时任务已存在，将被替换"
    # 移除旧的任务
    crontab -l 2>/dev/null | grep -v "$CLEANUP_SCRIPT" | crontab -
fi

# 添加新的 cron 任务（每天凌晨4点执行）
(crontab -l 2>/dev/null; echo "0 4 * * * $CLEANUP_SCRIPT >> $LOG_FILE 2>&1") | crontab -

echo "✅ 定时任务设置成功！"
echo ""
echo "当前定时任务列表："
crontab -l | grep -E "cleanup_result_cron|^#"
echo ""
echo "日志文件位置: $LOG_FILE"
echo ""
echo "如需手动执行清理，运行: $CLEANUP_SCRIPT"
echo "如需查看日志，运行: tail -f $LOG_FILE"

