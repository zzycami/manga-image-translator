# FC函数测试路径说明

## 当前状态

函数已经可以运行了！返回 `{"detail": "Not Found"}` 说明：
- ✅ 函数启动成功
- ✅ HTTP服务正常运行
- ⚠️ 访问的路径不存在

## 可用的API端点

根据 `fc_server.py`，可用的端点有：

### 1. 健康检查

**路径：** `/health`

**方法：** GET

**测试命令：**
```bash
curl https://your-function-url/health
```

**预期响应：**
```json
{"status":"ok"}
```

### 2. 根路径

**路径：** `/`

**方法：** GET

**测试命令：**
```bash
curl https://your-function-url/
```

**预期响应：**
```json
{
  "service": "Manga Translator",
  "version": "1.0.0",
  "endpoints": {
    "health": "/health",
    "translate": "/translate"
  }
}
```

### 3. 翻译接口

**路径：** `/translate`

**方法：** POST

**测试命令：**
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

## 测试步骤

### 步骤1：测试健康检查

在FC控制台测试功能中：
1. 方法选择：**GET**
2. 路径填写：`/health`
3. 点击 **"测试"**

或使用curl：
```bash
curl https://your-function-url/health
```

### 步骤2：测试根路径

在FC控制台测试功能中：
1. 方法选择：**GET**
2. 路径填写：`/`
3. 点击 **"测试"**

或使用curl：
```bash
curl https://your-function-url/
```

### 步骤3：测试翻译功能

在FC控制台测试功能中：
1. 方法选择：**POST**
2. 路径填写：`/translate`
3. 请求体填写：
```json
{
  "image_url": "https://example.com/image.jpg",
  "config": {
    "translator": {"translator": "deepseek"},
    "translator": {"target_lang": "CHS"}
  },
  "env": {
    "DEEPSEEK_API_KEY": "sk-fa51105a356949fa91dc262b7eea2aa6"
  }
}
```
4. 点击 **"测试"**

## 常见问题

### Q1: 为什么返回 "Not Found"？

**原因：**
- 访问的路径不存在
- 需要访问 `/health` 或 `/` 而不是其他路径

**解决方法：**
- 使用正确的路径：`/health` 或 `/`
- 检查路径是否正确

### Q2: 如何知道有哪些可用端点？

**方法：**
- 访问根路径 `/`，会返回所有可用端点
- 查看 `fc_server.py` 中的路由定义

## 推荐测试顺序

1. **先测试 `/health`**（最简单）
2. **再测试 `/`**（查看所有端点）
3. **最后测试 `/translate`**（完整功能）

## 下一步

请使用正确的路径测试：
- `/health` - 健康检查
- `/` - 根路径，查看所有端点
- `/translate` - 翻译功能

