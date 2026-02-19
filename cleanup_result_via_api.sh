#!/bin/bash

# 通过 API 清理 result 文件夹的脚本（推荐使用）
# 这种方式更安全，不会导致容器内的路径问题

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

API_URL="${MANGA_TRANSLATOR_API_URL:-http://localhost:8000}"
LOG_FILE="${SCRIPT_DIR}/cleanup_result.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========== 开始通过 API 清理 result 文件夹 =========="
log "API URL: $API_URL"

# 调用清理接口
response=$(curl -s -w "\n%{http_code}" -X DELETE "${API_URL}/results/clear" 2>&1)
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" -eq 200 ]; then
    log "清理成功: $body"
    log "========== 清理任务完成 =========="
    exit 0
else
    log "清理失败 - HTTP $http_code: $body"
    log "========== 清理任务失败 =========="
    exit 1
fi
