# FC流式响应部署说明

## ✅ 已完成

1. ✅ 修改 `fc_server.py` 添加流式响应支持
2. ✅ 添加 `/translate/with-form/image/stream` 端点
3. ✅ 实现流式响应逻辑（简化版，不使用队列）
4. ✅ 更新Kotlin配置使用FC地址

## 📋 修改内容

### 1. fc_server.py 修改

**新增功能：**
- 添加 `/translate/with-form/image/stream` 流式端点
- 实现 `stream_translation` 异步生成器
- 支持multipart/form-data格式（image文件和config JSON）
- 流式响应格式：1byte status + 4byte size + n byte data

**流式响应格式：**
- Status 0: 结果数据（图片）
- Status 1: 进度报告
- Status 2: 错误信息
- Status 3: 队列位置（FC环境不使用队列）

### 2. Kotlin配置更新

**application.yaml:**
```yaml
translate:
  local-manga:
    service-url: https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run
    timeout-seconds: 1800
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
  manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc-v2

# 推送镜像
docker push manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc-v2
```

### 步骤3：在FC中更新镜像

1. 在FC函数详情页面
2. 点击 **"配置"**（Configuration）标签
3. 找到 **"修改镜像"** 或 **"镜像地址"**
4. 更新镜像Tag为：`fc-v2`
5. 保存配置

### 步骤4：等待更新生效

- 等待几分钟让新镜像生效
- 或重新部署函数

## 🧪 测试步骤

### 测试1：健康检查

```bash
curl https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run/health
```

### 测试2：流式端点测试

使用Kotlin后端测试，或使用curl：

```bash
curl -X POST https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run/translate/with-form/image/stream \
  -F "image=@test.png" \
  -F 'config={"translator":{"translator":"deepseek","target_lang":"CHS"}}'
```

## 📝 注意事项

1. **流式响应格式**
   - 1byte status + 4byte size + n byte data
   - Status 0: 结果图片
   - Status 1: 进度报告
   - Status 2: 错误信息

2. **FC环境特点**
   - 不使用队列系统（简化实现）
   - 直接执行翻译
   - 支持长时间运行（超时时间600秒）

3. **Kotlin后端**
   - 已更新配置使用FC地址
   - 保持流式响应解析逻辑不变
   - 超时时间设置为1800秒

## 🎉 完成

修改完成后，Kotlin后端将调用FC函数进行翻译，支持流式响应和进度报告。

