# FC函数测试 - 正确路径

## ✅ 函数启动成功！

从日志看到：
- ✅ gunicorn服务器启动成功
- ✅ 应用启动完成
- ✅ 函数已就绪

## 📋 可用的API端点

根据 `fc_server.py`，可用的端点有：

### 1. 健康检查 ⭐ 推荐先测试这个

**路径：** `/health`

**方法：** GET

**在FC控制台测试：**
1. 方法选择：**GET**
2. 路径填写：`/health`
3. 点击 **"测试"**

**预期响应：**
```json
{"status":"ok"}
```

### 2. 根路径

**路径：** `/`

**方法：** GET

**在FC控制台测试：**
1. 方法选择：**GET**
2. 路径填写：`/`
3. 点击 **"测试"**

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

**在FC控制台测试：**
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

## 🔍 为什么之前返回 "Not Found"？

**可能原因：**
- 访问的路径不存在（如 `/test`、`/api` 等）
- 需要使用正确的路径：`/health` 或 `/`

**解决方法：**
- 使用正确的路径：`/health` 或 `/`
- 检查路径是否正确

## 📝 测试步骤

### 步骤1：测试健康检查（推荐先测试）

1. 在FC控制台，点击 **"测试"** 标签
2. 方法选择：**GET**
3. 路径填写：`/health`
4. 点击 **"测试"** 按钮

**预期结果：**
```json
{"status":"ok"}
```

### 步骤2：测试根路径

1. 方法选择：**GET**
2. 路径填写：`/`
3. 点击 **"测试"** 按钮

**预期结果：**
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

### 步骤3：测试翻译功能

1. 方法选择：**POST**
2. 路径填写：`/translate`
3. 请求体填写（见上方）
4. 点击 **"测试"** 按钮

## 🎉 恭喜！

函数已经成功启动并运行！现在只需要使用正确的路径测试即可。

## 下一步

1. **测试 `/health` 接口**（确认函数正常）
2. **测试 `/` 接口**（查看所有端点）
3. **测试 `/translate` 接口**（完整功能）

