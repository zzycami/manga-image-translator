# FC完整功能部署说明

## ✅ 已完成的功能

### 1. API接口
- ✅ `/health` - 健康检查
- ✅ `/translate` - 翻译接口（JSON）
- ✅ `/translate/with-form/image/stream` - 流式翻译接口（Form，兼容Kotlin后端）

### 2. Web UI界面
- ✅ `/` - Web管理界面（HTML）
- ✅ 服务状态查看
- ✅ 缓存文件管理
- ✅ 结果列表查看和删除

### 3. 状态和缓存管理
- ✅ `/status` - 获取服务状态
- ✅ `/queue-size` - 获取队列大小（FC环境返回0）
- ✅ `/results/list` - 列出所有结果目录
- ✅ `/results/clear` - 清空所有结果
- ✅ `/results/{folder_name}` - 删除指定结果

### 4. 静态文件服务
- ✅ `/result` - 静态文件服务（访问结果文件）

## 📋 功能说明

### Web UI界面

访问 `https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run/` 可以看到：

1. **服务状态**
   - 显示服务运行状态
   - 显示服务地址

2. **API端点列表**
   - 所有可用的API端点
   - 请求方法和路径

3. **缓存管理**
   - 查看结果列表
   - 删除指定结果
   - 清空所有缓存

### 状态查看

**GET /status**
```json
{
  "status": "running",
  "version": "1.0.0",
  "result_count": 5,
  "result_directory": "/tmp/result"
}
```

### 缓存管理

**GET /results/list**
```json
{
  "directories": ["result1", "result2", "result3"]
}
```

**DELETE /results/{folder_name}**
```json
{
  "message": "Deleted result directory: result1"
}
```

**DELETE /results/clear**
```json
{
  "message": "Deleted 5 result directories"
}
```

## 🚀 部署步骤

### 步骤1：重新构建镜像

```bash
cd /Users/zhouzeyong/Documents/GitHub/manga-image-translator

# 设置代理（如果需要）
export https_proxy=http://127.0.0.1:7890
export http_proxy=http://127.0.0.1:7890
export all_proxy=socks5://127.0.0.1:7890

# 重新构建镜像
docker build --platform linux/amd64 -f Dockerfile.fc.optimized -t manga-image-translator:fc-optimized .
```

### 步骤2：标记并推送镜像

```bash
# 标记镜像（使用新Tag）
docker tag manga-image-translator:fc-optimized \
  manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc-v3

# 推送镜像
docker push manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc-v3
```

### 步骤3：在FC中更新镜像

1. 在FC函数详情页面
2. 点击 **"配置"**（Configuration）标签
3. 找到 **"修改镜像"** 或 **"镜像地址"**
4. 更新镜像Tag为：`fc-v3`
5. 保存配置

### 步骤4：等待更新生效

- 等待几分钟让新镜像生效
- 或重新部署函数

## 🧪 测试步骤

### 测试1：Web UI界面

访问：
```
https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run/
```

应该能看到Web管理界面。

### 测试2：状态查看

```bash
curl https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run/status
```

### 测试3：结果列表

```bash
curl https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run/results/list
```

### 测试4：流式翻译

使用Kotlin后端测试，或使用curl：

```bash
curl -X POST https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run/translate/with-form/image/stream \
  -F "image=@test.png" \
  -F 'config={"translator":{"translator":"deepseek","target_lang":"CHS"}}'
```

## 📝 注意事项

### 1. 结果文件存储

- FC环境使用 `/tmp/result` 目录存储结果
- 结果文件在容器重启后会丢失（FC是无状态的）
- 如果需要持久化，建议使用OSS或其他存储服务

### 2. 缓存管理

- 可以通过Web UI或API管理缓存
- 删除操作不可恢复
- 建议定期清理缓存以节省空间

### 3. Web UI功能

- Web UI提供基本的管理功能
- 可以查看状态、管理缓存
- 不包含完整的翻译功能（使用API接口）

### 4. 队列系统

- FC环境不使用队列系统（无状态）
- `/queue-size` 始终返回0
- 每个请求独立处理

## 🎉 完成

现在FC函数支持：
- ✅ 流式翻译接口（兼容Kotlin后端）
- ✅ Web UI管理界面
- ✅ 状态查看
- ✅ 缓存管理

可以开始使用了！

