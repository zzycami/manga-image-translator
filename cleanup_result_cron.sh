#!/bin/bash

# 定期清理 result 文件夹的脚本
# 删除超过1天的文件夹，每天凌晨4点执行

RESULT_DIR="/root/manga-translator/result"
LOG_FILE="/root/manga-translator/cleanup_result.log"

# 记录日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 检查目录是否存在
if [ ! -d "$RESULT_DIR" ]; then
    log "错误: result 文件夹不存在: $RESULT_DIR"
    exit 1
fi

log "========== 开始清理任务 =========="
log "清理目录: $RESULT_DIR"

# 计算清理前的大小和数量
BEFORE_SIZE=$(du -sh "$RESULT_DIR" 2>/dev/null | cut -f1 || echo "0")
BEFORE_COUNT=$(find "$RESULT_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)

log "清理前 - 大小: $BEFORE_SIZE, 文件夹数: $BEFORE_COUNT"

# 删除超过1天的文件夹（mtime +1 表示超过1天）
log "正在删除超过1天的文件夹..."
find "$RESULT_DIR" -mindepth 1 -maxdepth 1 -type d -mtime +1 -exec rm -rf {} + 2>/dev/null

# 计算清理后的数量
AFTER_COUNT=$(find "$RESULT_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l)
AFTER_SIZE=$(du -sh "$RESULT_DIR" 2>/dev/null | cut -f1 || echo "0")
DELETED_COUNT=$((BEFORE_COUNT - AFTER_COUNT))

log "清理完成 - 删除了 $DELETED_COUNT 个文件夹, 剩余 $AFTER_COUNT 个"
log "清理前大小: $BEFORE_SIZE, 清理后大小: $AFTER_SIZE"
log "========== 清理任务完成 =========="
echo "" >> "$LOG_FILE"