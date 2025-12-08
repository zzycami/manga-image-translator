#!/bin/bash

# 漫画翻译服务启动脚本
# 使用方法: ./start_translation_service.sh [选项]

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 默认配置
HOST="0.0.0.0"
PORT=8000
USE_GPU=true
START_INSTANCE=true
VERBOSE=false
IGNORE_ERRORS=false
MODELS_TTL=0

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --no-gpu)
            USE_GPU=false
            shift
            ;;
        --no-instance)
            START_INSTANCE=false
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --ignore-errors)
            IGNORE_ERRORS=true
            shift
            ;;
        --models-ttl)
            MODELS_TTL="$2"
            shift 2
            ;;
        --help|-h)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --host HOST          服务监听地址 (默认: 0.0.0.0)"
            echo "  --port PORT          服务监听端口 (默认: 8000)"
            echo "  --no-gpu             不使用 GPU (使用 CPU)"
            echo "  --no-instance        不自动启动翻译实例"
            echo "  --verbose, -v        详细输出"
            echo "  --ignore-errors      忽略错误继续执行"
            echo "  --models-ttl SECONDS 模型缓存时间 (默认: 0, 永久缓存)"
            echo "  --help, -h           显示此帮助信息"
            echo ""
            exit 0
            ;;
        *)
            echo -e "${RED}错误: 未知参数 $1${NC}"
            echo "使用 --help 查看帮助信息"
            exit 1
            ;;
    esac
done

# 检查 Python 环境
echo -e "${YELLOW}检查 Python 环境...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 python3${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}✓${NC} $PYTHON_VERSION"

# 检查虚拟环境
VENV_DIR="$SCRIPT_DIR/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}警告: 未找到虚拟环境，尝试创建...${NC}"
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓${NC} 虚拟环境已创建"
fi

# 激活虚拟环境
echo -e "${YELLOW}激活虚拟环境...${NC}"
source "$VENV_DIR/bin/activate"
echo -e "${GREEN}✓${NC} 虚拟环境已激活"

# 检查依赖
echo -e "${YELLOW}检查依赖...${NC}"
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}警告: 缺少依赖，尝试安装...${NC}"
    pip install -r requirements.txt
fi
echo -e "${GREEN}✓${NC} 依赖检查完成"

# 检查 server 目录
SERVER_DIR="$SCRIPT_DIR/server"
if [ ! -d "$SERVER_DIR" ]; then
    echo -e "${RED}错误: 未找到 server 目录${NC}"
    exit 1
fi

# 构建启动命令
cd "$SERVER_DIR"
CMD="python main.py --host $HOST --port $PORT"

if [ "$USE_GPU" = true ]; then
    CMD="$CMD --use-gpu"
    echo -e "${GREEN}✓${NC} 启用 GPU 加速"
else
    echo -e "${YELLOW}⚠${NC} 使用 CPU 模式（性能较慢）"
fi

if [ "$START_INSTANCE" = true ]; then
    CMD="$CMD --start-instance"
    echo -e "${GREEN}✓${NC} 自动启动翻译实例"
fi

if [ "$VERBOSE" = true ]; then
    CMD="$CMD --verbose"
fi

if [ "$IGNORE_ERRORS" = true ]; then
    CMD="$CMD --ignore-errors"
fi

if [ "$MODELS_TTL" != "0" ]; then
    CMD="$CMD --models-ttl=$MODELS_TTL"
fi

# 显示启动信息
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  漫画翻译服务启动中...${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "服务地址: ${YELLOW}http://$HOST:$PORT${NC}"
echo -e "Web 界面: ${YELLOW}http://$HOST:$PORT${NC}"
echo -e "API 文档: ${YELLOW}http://$HOST:$PORT/docs${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 创建日志目录
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/translation_service_$(date +%Y%m%d_%H%M%S).log"

# 启动服务
echo -e "${YELLOW}启动服务...${NC}"
echo -e "日志文件: ${YELLOW}$LOG_FILE${NC}"
echo ""

# 捕获 Ctrl+C 信号
trap 'echo -e "\n${YELLOW}正在停止服务...${NC}"; exit 0' INT TERM

# 执行启动命令
if [ "$VERBOSE" = true ]; then
    # 详细模式：同时输出到控制台和日志文件
    $CMD 2>&1 | tee "$LOG_FILE"
else
    # 普通模式：输出到日志文件，控制台只显示关键信息
    $CMD 2>&1 | tee "$LOG_FILE" | grep -E "(Nonce|Starting|Uvicorn|Application startup|ERROR|WARNING)" || true
fi

