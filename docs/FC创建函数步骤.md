# 在阿里云FC中创建函数 - 详细步骤

## ✅ 已完成
- [x] 构建镜像
- [x] 标记镜像
- [x] 推送镜像到ACR

## 📋 下一步：在FC中创建函数

### 步骤1：登录阿里云控制台

1. 访问：https://fcnext.console.aliyun.com/
2. 选择您的地域（建议选择与ACR相同的地域，如：华东1-杭州）

### 步骤2：创建函数

1. 在函数列表页面，点击 **创建函数** 按钮（蓝色按钮）
2. 选择创建方式：
   - 选择 **使用容器镜像创建**（推荐）
   - 或者选择 **使用自定义运行时创建** → 然后选择 **容器镜像**

### 步骤4：配置函数基本信息

**函数配置：**
- **函数名称**：`manga-translator`（或自定义）
- **请求处理程序类型**：选择 **HTTP触发器**
- **运行环境**：选择 **Custom Container**

### 步骤5：配置容器镜像

**镜像配置：**
- **镜像地址**：`manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc`
- **镜像版本**：`fc`（或 `latest`）
- **容器端口**：`9000`
- **启动命令**：留空（使用镜像默认CMD）
- **启动参数**：留空

### 步骤6：配置函数规格

**资源配置：**
- **内存规格**：建议 `8192MB`（8GB）或更高
  - 最小建议：`4096MB`（4GB）
  - 推荐：`8192MB`（8GB）
  - 如果使用GPU：`16384MB`（16GB）

**GPU配置（如果需要）：**
- **是否启用GPU**：选择 **是**
- **GPU规格**：选择可用的GPU实例（如：`fc.gpu.tesla.1`）

**超时配置：**
- **执行超时时间**：`600秒`（10分钟）
  - 翻译一张图片可能需要几分钟，建议设置较长的超时时间

### 步骤7：配置环境变量

点击 **环境变量** 标签，添加以下环境变量：

| 变量名 | 变量值 | 说明 |
|--------|--------|------|
| `DEEPSEEK_API_KEY` | `sk-fa51105a356949fa91dc262b7eea2aa6` | DeepSeek API密钥 |
| `DEEPSEEK_API_BASE` | `https://api.deepseek.com` | DeepSeek API地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | DeepSeek模型名称 |
| `PYTHONUNBUFFERED` | `1` | Python输出不缓冲 |

### 步骤8：配置触发器

**HTTP触发器配置：**
- **触发方式**：选择 **HTTP触发器**
- **请求方法**：`GET,POST`（或根据需要选择）
- **认证方式**：选择 **匿名访问**（或根据需要配置）
- **路径**：`/*`（或自定义路径）

### 步骤9：高级配置（可选）

**VPC配置：**
- 如果需要访问VPC内的资源，可以配置VPC
- 通常不需要，除非要访问内网数据库等

**日志配置：**
- 建议启用日志功能，方便调试
- 日志保留时间：建议7天

### 步骤10：创建并测试

1. 检查所有配置无误后，点击 **创建**
2. 等待函数创建完成（可能需要几分钟）
3. 创建完成后，会显示函数的HTTP触发器地址

### 步骤11：测试函数

**健康检查：**
```bash
curl https://your-function-url/health
```

预期响应：
```json
{"status":"ok"}
```

**翻译测试：**
```bash
curl -X POST https://your-function-url/translate \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/image.jpg",
    "config": {
      "translator": {"translator": "deepseek"},
      "translator": {"target_lang": "CHS"}
    },
    "env": {
      "DEEPSEEK_API_KEY": "sk-fa51105a356949fa91dc262b7eea2aa6"
    }
  }'
```

## 重要配置总结

### 必须配置项
- ✅ 镜像地址：`manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc`
- ✅ 容器端口：`9000`
- ✅ 内存：至少 `4096MB`，推荐 `8192MB`
- ✅ 超时时间：`600秒`
- ✅ 环境变量：`DEEPSEEK_API_KEY` 等

### 推荐配置
- 启用日志功能
- 配置监控告警
- 设置合适的并发度

## 常见问题

### Q1: 函数启动失败
**A:** 
- 检查镜像地址是否正确
- 检查容器端口是否为9000
- 查看函数日志排查问题

### Q2: 函数超时
**A:** 
- 增加超时时间（最大600秒）
- 检查模型加载是否正常
- 优化图片大小

### Q3: 内存不足
**A:** 
- 增加内存规格
- 检查是否有内存泄漏
- 考虑使用GPU实例

### Q4: 无法访问函数
**A:** 
- 检查HTTP触发器是否已创建
- 检查认证方式配置
- 检查网络配置

## 下一步

函数创建成功后，可以：
1. 在FC控制台查看函数日志
2. 测试翻译接口
3. 配置监控和告警
4. 集成到您的Kotlin后端服务

