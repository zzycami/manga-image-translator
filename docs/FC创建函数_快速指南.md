# FC 3.0 创建函数 - 快速指南

## ✅ 当前状态
- 地域已选择：华东1（杭州）✅
- 在函数列表页面 ✅
- 准备创建函数

## 📋 创建函数步骤

### 步骤1：点击"创建函数"按钮

在函数列表页面，点击右上角的蓝色 **"创建函数"** 按钮。

### 步骤2：选择创建方式

选择 **"使用容器镜像创建"** 或 **"使用自定义运行时创建"** → 然后选择 **"容器镜像"**。

### 步骤3：配置函数基本信息

**函数配置：**
- **函数名称**：`manga-translator`（或自定义）
- **描述**：漫画翻译服务（可选）

### 步骤4：配置容器镜像（重要！）

**镜像配置：**
- **镜像地址**：`manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc`
- **镜像版本**：`fc`（或留空使用latest）
- **容器端口**：`9000` ⚠️ **必须设置为9000**
- **启动命令**：留空（使用镜像默认CMD）
- **启动参数**：留空

### 步骤5：配置函数规格

**资源配置：**
- **内存规格**：
  - 最小：`4096MB`（4GB）
  - 推荐：`8192MB`（8GB）
  - 如果使用GPU：`16384MB`（16GB）

**GPU配置（可选，如果需要）：**
- **是否启用GPU**：选择 **是**
- **GPU规格**：选择可用的GPU实例（如：`fc.gpu.tesla.1`）

**超时配置：**
- **执行超时时间**：`600秒`（10分钟）
  - 翻译一张图片可能需要几分钟，建议设置较长的超时时间

### 步骤6：配置环境变量

添加以下环境变量：

| 变量名 | 变量值 | 说明 |
|--------|--------|------|
| `DEEPSEEK_API_KEY` | `sk-fa51105a356949fa91dc262b7eea2aa6` | DeepSeek API密钥 |
| `DEEPSEEK_API_BASE` | `https://api.deepseek.com` | DeepSeek API地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | DeepSeek模型名称 |
| `PYTHONUNBUFFERED` | `1` | Python输出不缓冲 |

### 步骤7：配置HTTP触发器

**触发器配置：**
- **触发方式**：选择 **HTTP触发器**
- **请求方法**：`GET,POST`（或根据需要选择）
- **认证方式**：选择 **匿名访问**（或根据需要配置）
- **路径**：`/*`（或自定义路径，如 `/translate`）

### 步骤8：创建并等待

1. 检查所有配置无误后，点击 **创建**
2. 等待函数创建完成（可能需要几分钟）
3. 创建完成后，会显示函数的HTTP触发器地址

### 步骤9：测试函数

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

## 🔑 关键配置项总结

### 必须配置
- ✅ **镜像地址**：`manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc`
- ✅ **容器端口**：`9000`
- ✅ **内存**：至少 `4096MB`，推荐 `8192MB`
- ✅ **超时时间**：`600秒`
- ✅ **环境变量**：`DEEPSEEK_API_KEY` 等

### 推荐配置
- 启用日志功能
- 配置监控告警
- 设置合适的并发度

## ⚠️ 注意事项

1. **容器端口必须设置为9000**，这是 `fc_server.py` 监听的端口
2. **内存建议至少8GB**，因为镜像包含所有模型
3. **超时时间建议600秒**，翻译可能需要较长时间
4. **确保ACR镜像可访问**，函数需要能拉取镜像

## 下一步

创建完成后，告诉我函数地址，我可以帮您测试！

