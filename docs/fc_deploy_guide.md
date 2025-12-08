# 阿里云函数计算部署指南

## 前置准备

### 1. 阿里云账号准备
- 注册并实名认证阿里云账号
- 开通函数计算服务（FC）
- 开通容器镜像服务（ACR）
- 获取AccessKey ID和Secret

### 2. 安装工具
```bash
# 安装Docker
# macOS: brew install docker
# 或下载Docker Desktop

# 安装阿里云CLI（可选）
# macOS: brew install aliyun-cli
# 或访问: https://help.aliyun.com/document_detail/110341.html

# 安装Fun工具（推荐，更简单）
npm install @alicloud/fun -g
```

## 部署步骤

### 方法1: 使用Fun工具部署（推荐）

#### 1. 配置Fun工具
```bash
fun config
# 输入AccessKey ID和Secret
# 选择区域（如：cn-hangzhou）
```

#### 2. 构建并推送镜像
```bash
# 登录ACR
docker login --username=your-username registry.cn-hangzhou.aliyuncs.com

# 构建镜像
docker build -f Dockerfile.fc -t manga-image-translator:fc .

# 标记镜像（替换为您的ACR地址）
docker tag manga-image-translator:fc \
  registry.cn-hangzhou.aliyuncs.com/your-namespace/manga-image-translator:fc

# 推送镜像
docker push registry.cn-hangzhou.aliyuncs.com/your-namespace/manga-image-translator:fc
```

#### 3. 修改配置文件
编辑 `fc_config.yaml`，更新：
- `image`: 您的ACR镜像地址
- `region`: 您的区域
- `accessKeyId` 和 `accessKeySecret`: 环境变量或直接填写

#### 4. 部署函数
```bash
fun deploy
```

### 方法2: 使用阿里云控制台部署

#### 1. 准备镜像
```bash
# 构建镜像
docker build -f Dockerfile.fc -t manga-image-translator:fc .

# 推送到ACR（在控制台创建仓库后）
docker tag manga-image-translator:fc \
  registry.cn-hangzhou.aliyuncs.com/your-namespace/manga-image-translator:fc
docker push registry.cn-hangzhou.aliyuncs.com/your-namespace/manga-image-translator:fc
```

#### 2. 在控制台创建服务
1. 登录 [函数计算控制台](https://fcnext.console.aliyun.com/)
2. 创建服务：`manga-translator`
3. 创建函数：
   - 函数名称：`translate`
   - 运行环境：Custom Container
   - 镜像地址：`registry.cn-hangzhou.aliyuncs.com/your-namespace/manga-image-translator:fc`
   - 内存：8192 MB
   - 超时时间：600秒
   - GPU显存：16384 MB（如果选择GPU实例）

#### 3. 创建HTTP触发器
- 触发器类型：HTTP触发器
- 认证方式：匿名访问（或配置认证）
- 请求方法：GET, POST

## 配置说明

### 资源配置
- **内存**: 建议8192MB（8GB）或更高
- **超时**: 建议600秒（10分钟），翻译可能需要较长时间
- **GPU**: 如果使用GPU加速，需要选择GPU实例类型
- **磁盘**: 默认512MB，如果模型文件较大，建议使用NAS挂载

### 环境变量
可以在函数配置中设置：
```yaml
DEEPSEEK_API_KEY: your-api-key
DEEPSEEK_API_BASE: https://api.deepseek.com
MODEL_DIR: /mnt/auto/models  # 如果使用NAS
```

### 模型文件处理

**方案1: 打包到镜像（不推荐，镜像会很大）**
- 修改Dockerfile，取消注释模型准备步骤
- 镜像会非常大（可能>20GB）

**方案2: 使用NAS挂载（推荐）**
1. 创建NAS文件系统
2. 在函数配置中挂载NAS
3. 将模型文件上传到NAS
4. 设置环境变量 `MODEL_DIR=/mnt/auto/models`

**方案3: 使用OSS（推荐）**
1. 将模型文件上传到OSS
2. 函数启动时从OSS下载模型（首次调用会慢）
3. 缓存到 `/tmp` 目录（函数计算提供）

## 测试函数

### 1. 健康检查
```bash
curl https://your-service-name-translate.cn-hangzhou.fcapp.run/health
```

### 2. 测试翻译
```bash
curl -X POST https://your-service-name-translate.cn-hangzhou.fcapp.run/translate \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/image.png",
    "config": {
      "translator": {
        "translator": "deepseek",
        "target_lang": "CHS"
      }
    },
    "env": {
      "DEEPSEEK_API_KEY": "your-api-key"
    }
  }'
```

## 成本优化

### 1. 使用试用额度
- 每月15万CU免费额度
- 3个月试用期
- 合理配置资源，充分利用免费额度

### 2. 资源优化
- 根据实际需求调整内存和GPU配置
- 使用预留实例减少冷启动
- 合理设置超时时间

### 3. 模型优化
- 使用NAS或OSS存储模型，避免镜像过大
- 实现模型缓存机制
- 考虑使用更小的模型

## 监控和日志

### 查看日志
```bash
# 使用Fun工具
fun logs

# 或访问控制台
# 函数计算 -> 服务 -> 函数 -> 日志
```

### 监控指标
- 函数调用次数
- 执行时间
- 错误率
- 资源使用情况

## 常见问题

### 1. 冷启动慢
- 使用预留实例
- 减少镜像大小
- 优化启动代码

### 2. 内存不足
- 增加内存配置
- 优化模型加载
- 使用更小的模型

### 3. 超时
- 增加超时时间
- 优化翻译流程
- 考虑异步处理

### 4. GPU不可用
- 确认选择了GPU实例类型
- 检查CUDA版本兼容性
- 查看函数日志

## 下一步

部署成功后，可以：
1. 集成到Kotlin服务端
2. 实现进度回调
3. 配置自动扩缩容
4. 设置监控告警


