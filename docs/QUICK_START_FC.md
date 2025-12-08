# 快速开始：部署到阿里云函数计算

## 前置条件

1. ✅ 阿里云账号（已实名认证）
2. ✅ 开通函数计算服务
3. ✅ 开通容器镜像服务（ACR）
4. ✅ 获取AccessKey（用于CLI工具）

## 快速部署（5步）

### 步骤1: 准备ACR仓库

1. 登录 [容器镜像服务控制台](https://cr.console.aliyun.com/)
2. 创建命名空间（如：`manga-translator`）
3. 创建镜像仓库（如：`manga-image-translator`）
4. 记录仓库地址：`registry.cn-hangzhou.aliyuncs.com/your-namespace/manga-image-translator`

### 步骤2: 构建并推送镜像

```bash
# 登录ACR（替换为您的地址）
docker login registry.cn-hangzhou.aliyuncs.com

# 构建镜像
docker build -f Dockerfile.fc -t manga-image-translator:fc .

# 标记镜像（替换为您的ACR地址）
docker tag manga-image-translator:fc \
  registry.cn-hangzhou.aliyuncs.com/your-namespace/manga-image-translator:fc

# 推送镜像
docker push registry.cn-hangzhou.aliyuncs.com/your-namespace/manga-image-translator:fc
```

### 步骤3: 在控制台创建服务

1. 登录 [函数计算控制台](https://fcnext.console.aliyun.com/)
2. 选择区域（如：华东1-杭州）
3. 点击"创建服务"
   - 服务名称：`manga-translator`
   - 描述：漫画翻译服务
   - 点击"确定"

### 步骤4: 创建函数

在服务中点击"创建函数"：

**基本信息**
- 函数名称：`translate`
- 运行环境：**Custom Container**
- 镜像地址：`registry.cn-hangzhou.aliyuncs.com/your-namespace/manga-image-translator:fc`

**高级配置**
- 内存规格：**8192 MB**（8GB）
- 超时时间：**600秒**（10分钟）
- GPU显存：**16384 MB**（16GB，如果使用GPU）
- 实例并发度：1（建议）

**环境变量**（可选）
```
DEEPSEEK_API_KEY=your-api-key
DEEPSEEK_API_BASE=https://api.deepseek.com
MODEL_DIR=/tmp/models
```

点击"创建"

### 步骤5: 创建HTTP触发器

在函数详情页，点击"触发器" -> "创建触发器"：

- 触发器类型：**HTTP触发器**
- 触发器名称：`httpTrigger`
- 认证方式：**匿名访问**（测试用，生产环境建议配置认证）
- 请求方法：**GET, POST**
- 路径：`/*`

点击"确定"

## 测试部署

### 1. 获取函数URL

在函数详情页的"触发器"中，可以看到HTTP触发器的公网访问地址：
```
https://manga-translator-translate.cn-hangzhou.fcapp.run
```

### 2. 健康检查

```bash
curl https://manga-translator-translate.cn-hangzhou.fcapp.run/health
```

应该返回：
```json
{"status":"ok"}
```

### 3. 测试翻译

```bash
curl -X POST https://manga-translator-translate.cn-hangzhou.fcapp.run/translate \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/test-image.png",
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

## 重要提示

### 模型文件处理

由于模型文件很大（可能>10GB），建议：

**方案1: 使用NAS挂载（推荐）**
1. 创建NAS文件系统
2. 上传模型到NAS
3. 在函数配置中挂载NAS到 `/mnt/auto/models`
4. 设置环境变量 `MODEL_DIR=/mnt/auto/models`

**方案2: 首次调用时下载**
- 修改代码，首次调用时从OSS下载模型
- 缓存到 `/tmp` 目录
- 后续调用直接使用缓存

**方案3: 打包到镜像（不推荐）**
- 镜像会非常大（>20GB）
- 推送和拉取都很慢
- 占用大量存储空间

### 成本优化

1. **使用试用额度**
   - 每月15万CU免费
   - 合理配置资源

2. **资源配置建议**
   - 测试环境：4096MB内存，无GPU
   - 生产环境：8192MB内存，16384MB GPU

3. **超时设置**
   - 根据实际翻译时间调整
   - 避免设置过长导致资源浪费

## 常见问题

### Q: 镜像太大，推送失败？
A: 使用NAS或OSS存储模型，不要打包到镜像中

### Q: 函数超时？
A: 增加超时时间，或优化翻译流程

### Q: 内存不足？
A: 增加内存配置，或使用更小的模型

### Q: GPU不可用？
A: 确认选择了GPU实例类型，检查CUDA版本

## 下一步

部署成功后：
1. 集成到Kotlin服务端
2. 实现进度回调
3. 配置监控告警
4. 优化性能和成本


