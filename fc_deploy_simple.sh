#!/bin/bash

# FC GPU 快速部署脚本（简化版）
# 用于早期验证

set -e

# ==================== 配置区域（请修改）====================
REGION="cn-hangzhou"                    # 函数计算区域
SERVICE_NAME="manga-translator"         # 服务名称
FUNCTION_NAME="translate"               # 函数名称
ACR_REGISTRY="registry.cn-hangzhou.aliyuncs.com/your-namespace"  # ACR 地址（请修改）
ACR_USERNAME=""                         # ACR 用户名（请修改）
ACR_PASSWORD=""                         # ACR 密码（请修改，或使用环境变量）
IMAGE_NAME="manga-image-translator:fc"  # 镜像名称
DEEPSEEK_API_KEY="sk-fa51105a356949fa91dc262b7eea2aa6"  # DeepSeek API Key
# ==========================================================

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  FC GPU 快速部署脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查配置
if [ -z "$ACR_REGISTRY" ] || [ "$ACR_REGISTRY" = "registry.cn-hangzhou.aliyuncs.com/your-namespace" ]; then
    echo -e "${RED}错误: 请先配置 ACR_REGISTRY${NC}"
    echo -e "${YELLOW}编辑脚本，修改 ACR_REGISTRY 为您的实际地址${NC}"
    exit 1
fi

if [ -z "$ACR_USERNAME" ]; then
    echo -e "${YELLOW}提示: 未设置 ACR_USERNAME，将使用环境变量或交互式登录${NC}"
fi

# 步骤1: 构建镜像
echo -e "${GREEN}[1/5] 构建 Docker 镜像...${NC}"
docker build -f Dockerfile.fc -t ${IMAGE_NAME} . || {
    echo -e "${RED}镜像构建失败！${NC}"
    exit 1
}
echo -e "${GREEN}✓ 镜像构建完成${NC}"
echo ""

# 步骤2: 标记镜像
echo -e "${GREEN}[2/5] 标记镜像...${NC}"
FULL_IMAGE_NAME="${ACR_REGISTRY}/${IMAGE_NAME}"
docker tag ${IMAGE_NAME} ${FULL_IMAGE_NAME}
echo -e "${GREEN}✓ 镜像标记完成${NC}"
echo ""

# 步骤3: 登录 ACR
echo -e "${GREEN}[3/5] 登录阿里云容器镜像服务...${NC}"
if [ -n "$ACR_PASSWORD" ]; then
    echo "$ACR_PASSWORD" | docker login --username=${ACR_USERNAME} --password-stdin ${ACR_REGISTRY}
else
    docker login --username=${ACR_USERNAME} ${ACR_REGISTRY}
fi
echo -e "${GREEN}✓ 登录成功${NC}"
echo ""

# 步骤4: 推送镜像
echo -e "${GREEN}[4/5] 推送镜像到 ACR...${NC}"
echo -e "${YELLOW}提示: 镜像较大，可能需要 10-30 分钟，请耐心等待...${NC}"
docker push ${FULL_IMAGE_NAME} || {
    echo -e "${RED}镜像推送失败！${NC}"
    exit 1
}
echo -e "${GREEN}✓ 镜像推送完成${NC}"
echo ""

# 步骤5: 提示手动创建函数
echo -e "${GREEN}[5/5] 准备创建函数...${NC}"
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  镜像已准备就绪！${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}接下来请在阿里云控制台手动创建函数：${NC}"
echo ""
echo -e "1. 访问: ${BLUE}https://fcnext.console.aliyun.com/${NC}"
echo -e "2. 创建服务: ${GREEN}${SERVICE_NAME}${NC}"
echo -e "3. 创建函数，配置如下："
echo ""
echo -e "   ${GREEN}函数名称${NC}: ${FUNCTION_NAME}"
echo -e "   ${GREEN}运行环境${NC}: Custom Container"
echo -e "   ${GREEN}镜像地址${NC}: ${FULL_IMAGE_NAME}"
echo -e "   ${GREEN}内存规格${NC}: 8192 MB"
echo -e "   ${GREEN}超时时间${NC}: 600 秒"
echo -e "   ${GREEN}实例类型${NC}: GPU 实例"
echo -e "   ${GREEN}GPU 显存${NC}: 16384 MB"
echo ""
echo -e "   ${GREEN}环境变量${NC}:"
echo -e "     PYTHONUNBUFFERED=1"
echo -e "     DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}"
echo -e "     DEEPSEEK_API_BASE=https://api.deepseek.com"
echo -e "     DEEPSEEK_MODEL=deepseek-chat"
echo ""
echo -e "4. 创建 HTTP 触发器（匿名访问）"
echo ""
echo -e "${BLUE}========================================${NC}"
echo ""

# 可选：使用阿里云 CLI 自动创建（如果已安装）
if command -v aliyun &> /dev/null; then
    read -p "是否使用阿里云 CLI 自动创建函数？(y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}使用阿里云 CLI 创建函数...${NC}"
        
        # 创建服务
        aliyun fc CreateService \
            --region ${REGION} \
            --serviceName ${SERVICE_NAME} \
            --description "漫画翻译服务" 2>/dev/null || echo "服务已存在，跳过"
        
        # 创建函数
        aliyun fc CreateFunction \
            --region ${REGION} \
            --serviceName ${SERVICE_NAME} \
            --functionName ${FUNCTION_NAME} \
            --runtime custom \
            --handler index.handler \
            --code "{\"image\":\"${FULL_IMAGE_NAME}\"}" \
            --memorySize 8192 \
            --timeout 600 \
            --gpuMemorySize 16384 \
            --environmentVariables "{\"PYTHONUNBUFFERED\":\"1\",\"DEEPSEEK_API_KEY\":\"${DEEPSEEK_API_KEY}\",\"DEEPSEEK_API_BASE\":\"https://api.deepseek.com\",\"DEEPSEEK_MODEL\":\"deepseek-chat\"}" 2>/dev/null || \
        aliyun fc UpdateFunction \
            --region ${REGION} \
            --serviceName ${SERVICE_NAME} \
            --functionName ${FUNCTION_NAME} \
            --code "{\"image\":\"${FULL_IMAGE_NAME}\"}" \
            --memorySize 8192 \
            --timeout 600 \
            --gpuMemorySize 16384 \
            --environmentVariables "{\"PYTHONUNBUFFERED\":\"1\",\"DEEPSEEK_API_KEY\":\"${DEEPSEEK_API_KEY}\",\"DEEPSEEK_API_BASE\":\"https://api.deepseek.com\",\"DEEPSEEK_MODEL\":\"deepseek-chat\"}"
        
        echo -e "${GREEN}✓ 函数创建/更新完成${NC}"
        echo ""
        echo -e "${BLUE}函数 URL:${NC}"
        echo -e "${GREEN}https://${SERVICE_NAME}-${FUNCTION_NAME}.${REGION}.fcapp.run${NC}"
    fi
fi

echo ""
echo -e "${GREEN}部署脚本执行完成！${NC}"

