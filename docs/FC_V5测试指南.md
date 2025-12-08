# FC V5版本测试指南

## ✅ 镜像已更新

FC控制台显示：**镜像资源准备完成**

## 🧪 测试步骤

### 测试1：健康检查

```bash
curl https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run/health
```

**预期响应：**
```json
{"status":"ok"}
```

### 测试2：服务状态

```bash
curl https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run/status
```

**预期响应：**
```json
{
  "status": "running",
  "version": "1.0.0",
  "result_count": 0,
  "result_directory": "/tmp/result"
}
```

### 测试3：Web UI界面

访问浏览器：
```
https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run/
```

应该能看到Web管理界面。

### 测试4：Kotlin后端翻译

启动Kotlin后端，调用翻译接口，应该：
- ✅ 不再出现 `'Config' object has no attribute 'get'` 错误
- ✅ 翻译正常进行
- ✅ 流式进度报告正常工作

## 🔍 如果还有错误

### 检查1：查看FC函数日志

在FC控制台查看函数日志，确认：
- 使用的是新镜像（fc-v5）
- 没有Config对象错误
- 翻译正常进行

### 检查2：验证代码

确认本地代码已修复：
```bash
cd /Users/zhouzeyong/Documents/GitHub/manga-image-translator
grep -n "MangaTranslator(config)" fc_server.py
# 应该没有输出
```

### 检查3：等待生效

如果还是报错，可能是：
- 镜像还没有完全生效（等待几分钟）
- 需要重新触发一次请求
- 查看FC函数日志确认错误信息

## 📝 修复内容总结

### 1. Config对象错误修复
- ✅ `MangaTranslator.__init__` 使用字典参数（translator_params）
- ✅ `translate()` 方法使用Config对象
- ✅ 从返回的Context对象中获取结果

### 2. Kotlin代码优化
- ✅ 发送完整的参数字典（包含translator_params和config）
- ✅ 简化FC函数的配置解析

### 3. 流式进度报告
- ✅ 使用进度hook实现实时进度报告
- ✅ 支持流式传输进度信息

## 🎉 完成

现在可以测试翻译功能了！如果还有问题，请查看FC函数日志并告诉我具体的错误信息。

