#!/bin/bash
# 阿里云函数计算部署脚本

set -e

# 配置信息（请修改为您的实际值）
REGION="cn-hangzhou"  # 函数计算区域
SERVICE_NAME="manga-translator"  # 服务名称
FUNCTION_NAME="translate"  # 函数名称
IMAGE_NAME="manga-image-translator:fc"  # Docker镜像名称
ACR_REGISTRY=""  # 阿里云容器镜像服务地址，格式：registry.cn-hangzhou.aliyuncs.com/namespace

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}开始部署到阿里云函数计算...${NC}"

# 1. 检查是否已登录阿里云
if ! command -v aliyun &> /dev/null; then
    echo -e "${YELLOW}警告: 未安装阿里云CLI，请先安装: https://help.aliyun.com/document_detail/110341.html${NC}"
    echo -e "${YELLOW}或者使用阿里云控制台手动部署${NC}"
fi

# 2. 构建Docker镜像
echo -e "${GREEN}步骤1: 构建Docker镜像...${NC}"
docker build -f Dockerfile.fc -t ${IMAGE_NAME} .

if [ -z "$ACR_REGISTRY" ]; then
    echo -e "${YELLOW}提示: 未设置ACR_REGISTRY，请手动推送到阿里云容器镜像服务${NC}"
    echo -e "${YELLOW}1. 登录阿里云容器镜像服务: https://cr.console.aliyun.com${NC}"
    echo -e "${YELLOW}2. 创建命名空间和仓库${NC}"
    echo -e "${YELLOW}3. 推送镜像: docker tag ${IMAGE_NAME} ${ACR_REGISTRY}/${IMAGE_NAME}${NC}"
    echo -e "${YELLOW}4. docker push ${ACR_REGISTRY}/${IMAGE_NAME}${NC}"
    exit 0
fi

# 3. 标记镜像
echo -e "${GREEN}步骤2: 标记镜像...${NC}"
docker tag ${IMAGE_NAME} ${ACR_REGISTRY}/${IMAGE_NAME}

# 4. 登录ACR
echo -e "${GREEN}步骤3: 登录阿里云容器镜像服务...${NC}"
docker login --username=${ACR_USERNAME} --password=${ACR_PASSWORD} ${ACR_REGISTRY}

# 5. 推送镜像
echo -e "${GREEN}步骤4: 推送镜像到ACR...${NC}"
docker push ${ACR_REGISTRY}/${IMAGE_NAME}

# 6. 创建或更新函数
echo -e "${GREEN}步骤5: 创建/更新函数...${NC}"

# 使用阿里云CLI创建服务（如果不存在）
aliyun fc CreateService \
    --region ${REGION} \
    --serviceName ${SERVICE_NAME} \
    --description "漫画翻译服务" || echo "服务已存在，跳过创建"

# 创建或更新函数
aliyun fc CreateFunction \
    --region ${REGION} \
    --serviceName ${SERVICE_NAME} \
    --functionName ${FUNCTION_NAME} \
    --runtime custom \
    --handler index.handler \
    --code "{\"image\":\"${ACR_REGISTRY}/${IMAGE_NAME}\"}" \
    --memorySize 8192 \
    --timeout 600 \
    --gpuMemorySize 16384 \
    --environmentVariables "{\"PYTHONUNBUFFERED\":\"1\"}" || \
aliyun fc UpdateFunction \
    --region ${REGION} \
    --serviceName ${SERVICE_NAME} \
    --functionName ${FUNCTION_NAME} \
    --code "{\"image\":\"${ACR_REGISTRY}/${IMAGE_NAME}\"}" \
    --memorySize 8192 \
    --timeout 600 \
    --gpuMemorySize 16384

# 7. 创建HTTP触发器
echo -e "${GREEN}步骤6: 创建HTTP触发器...${NC}"
aliyun fc CreateTrigger \
    --region ${REGION} \
    --serviceName ${SERVICE_NAME} \
    --functionName ${FUNCTION_NAME} \
    --triggerName httpTrigger \
    --triggerType http \
    --triggerConfig "{\"authType\":\"anonymous\",\"methods\":[\"GET\",\"POST\"]}" || \
echo "触发器已存在，跳过创建"

echo -e "${GREEN}部署完成！${NC}"
echo -e "${GREEN}函数URL: https://${SERVICE_NAME}-${FUNCTION_NAME}.${REGION}.fcapp.run${NC}"


