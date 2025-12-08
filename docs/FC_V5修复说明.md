# FC V5版本修复说明

## ✅ 已修复的问题

### 1. Config对象错误
- **问题**：`MangaTranslator.__init__` 期望接收字典，但传递了Config对象
- **修复**：创建 `MangaTranslator` 时传递字典参数

### 2. 流式进度报告
- **新增**：使用进度hook实现实时进度报告
- **功能**：类似队列系统，支持流式传输进度信息

## 📋 主要改进

### 1. 使用进度Hook
```python
# 添加进度hook，将进度信息发送到队列
async def progress_hook(state: str, finished: bool):
    state_data = state.encode('utf-8')
    progress_data = b'\x01' + len(state_data).to_bytes(4, 'big') + state_data
    await progress_queue.put(progress_data)

translator.add_progress_hook(progress_hook)
```

### 2. 流式传输进度
- 实时发送翻译进度（upscaling, detection, ocr, translating, rendering等）
- 支持错误处理和结果返回

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
  manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc-v5

# 推送镜像
docker push manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc-v5
```

### 步骤3：在FC中更新镜像

1. 登录阿里云控制台
2. 进入函数计算（FC）服务
3. 找到函数：`manga-translator`
4. 点击函数名称进入详情页面
5. 点击 **"配置"**（Configuration）标签
6. 找到 **"修改镜像"** 或 **"镜像地址"**
7. 更新镜像Tag为：`fc-v5`
8. **重要**：点击 **"保存"** 或 **"更新"**
9. **等待几分钟**让新镜像生效

### 步骤4：验证镜像更新

在FC函数日志中查看，应该能看到：
- 没有 `'Config' object has no attribute 'get'` 错误
- 翻译正常进行
- 进度信息正常输出

## 🔍 如果还是报错

### 检查1：确认镜像Tag已更新

在FC控制台检查镜像地址是否为：
```
manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc-v5
```

### 检查2：等待镜像生效

更新镜像后，需要等待几分钟让新镜像生效。可以：
- 查看FC函数日志
- 重新触发一次请求
- 检查错误信息是否变化

### 检查3：清除缓存

如果还是报错，可以尝试：
1. 在FC控制台重新部署函数
2. 或者等待一段时间后重试

## 📝 新功能

### 流式进度报告

现在支持实时进度报告，包括：
- `upscaling` - 图片放大
- `detection` - 文本检测
- `ocr` - 文字识别
- `translating` - 文本翻译
- `rendering` - 文字渲染
- `colorizing` - 颜色处理
- `downscaling` - 图片缩小

这些进度信息会实时流式传输到Kotlin后端。

## 🎉 完成

修复完成后，应该能够：
- ✅ 正常创建 `MangaTranslator` 实例
- ✅ 正常执行翻译
- ✅ 实时获取翻译进度
- ✅ 流式返回翻译结果

