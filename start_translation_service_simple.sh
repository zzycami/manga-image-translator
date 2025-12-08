#!/bin/bash

# 漫画翻译服务启动脚本（简化版）
# 快速启动，使用默认配置

set -e

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 设置 DeepSeek API Key
export DEEPSEEK_API_KEY="sk-fa51105a356949fa91dc262b7eea2aa6"
export DEEPSEEK_API_BASE="https://api.deepseek.com"
export DEEPSEEK_MODEL="deepseek-chat"

# 激活虚拟环境
source venv/bin/activate

# 切换到 server 目录并启动服务
cd server
python main.py --start-instance --use-gpu --host 0.0.0.0 --port 8000

