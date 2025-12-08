# FC函数后续配置步骤

## ✅ 已配置项
- [x] 函数名称：`manga-translator`
- [x] 实例类型：弹性实例
- [x] GPU卡型：Ada 系列
- [x] 规格方案：默认值
- [x] 最小实例数：1
- [x] 单实例并发度：20
- [x] 磁盘：60GB

## 📋 接下来需要配置

### 1. 函数代码（关键配置）

#### 运行环境
- ✅ 应该已经选择：**自定义镜像/使用ACR中的镜像**

#### 容器镜像 ⚠️ **重要**
1. 点击 **"选择 ACR 中的镜像"** 按钮
2. 在弹出的对话框中，选择：
   ```
   manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc
   ```
3. 或者直接在输入框中输入上述镜像地址

#### 启动命令
- **留空**（使用镜像默认CMD）
- 镜像中已经配置了：`gunicorn fc_server:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:9000 --timeout 600`

#### 监听端口 ⚠️ **必须填写**
- 填写：`9000`
- 这是我们的 `fc_server.py` 监听的端口

#### 执行超时时间 ⚠️ **需要修改**
- 当前默认值可能是：`60秒`
- **改为**：`600秒`（10分钟）
- 翻译任务可能需要几分钟，需要较长的超时时间

### 2. 实例预热（可选）

- **保持关闭**（默认）
- 如果需要优化冷启动，可以后续开启

### 3. 高级配置

#### 网络 ✅ **已正确配置**
- ✅ **允许默认网卡访问公网**：应该已经开启（绿色）
- 这是必需的，因为需要访问DeepSeek API

#### 环境变量 ⚠️ **必须添加**

1. 展开 **"更多配置"** 部分
2. 找到 **"环境变量"** 选项
3. 点击添加环境变量，添加以下4个：

| 变量名 | 变量值 | 说明 |
|--------|--------|------|
| `DEEPSEEK_API_KEY` | `sk-fa51105a356949fa91dc262b7eea2aa6` | DeepSeek API密钥 |
| `DEEPSEEK_API_BASE` | `https://api.deepseek.com` | DeepSeek API地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | DeepSeek模型名称 |
| `PYTHONUNBUFFERED` | `1` | Python输出不缓冲 |

#### 日志（推荐开启）

1. 展开 **"日志、链路追踪"** 部分
2. 开启 **"日志"** 功能
3. 方便后续调试和排查问题

#### 其他配置（保持默认）

- **权限**：保持默认
- **存储**：保持默认（如果需要持久化，可以挂载NAS或OSS）
- **隔离性、亲和性**：保持默认

## 🔑 关键配置检查清单

在点击"创建"之前，确认以下配置：

- [ ] **容器镜像**：已选择ACR中的镜像
- [ ] **监听端口**：填写了 `9000`
- [ ] **执行超时时间**：改为 `600秒`
- [ ] **环境变量**：已添加4个环境变量（DEEPSEEK相关）
- [ ] **允许访问公网**：已开启
- [ ] **日志**：建议开启

## 创建后的步骤

### 1. 等待函数创建完成
- 可能需要几分钟
- 创建完成后会显示函数详情页面

### 2. 创建HTTP触发器

函数创建后，需要创建HTTP触发器：

1. 在函数详情页面，找到 **"触发器"** 或 **"HTTP触发器"** 选项
2. 点击 **"创建触发器"**
3. 配置：
   - **触发方式**：HTTP触发器
   - **请求方法**：`GET,POST`（或根据需要选择）
   - **认证方式**：匿名访问（或根据需要配置）
   - **路径**：`/*`（或自定义路径）
4. 创建触发器

### 3. 获取函数访问地址

创建HTTP触发器后，会显示函数的访问地址，类似：
```
https://your-function-name.cn-hangzhou.fcapp.run
```

### 4. 测试函数

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

## 注意事项

1. **镜像Tag**：FC会使用创建函数时镜像Tag对应的Digest，不要重复推送覆盖此Tag
2. **超时时间**：翻译任务可能需要几分钟，确保设置为600秒
3. **环境变量**：确保DeepSeek API密钥正确
4. **公网访问**：确保已开启，否则无法访问DeepSeek API

