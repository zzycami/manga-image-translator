# FC函数测试指南

## ✅ 当前状态

- ✅ 函数已创建成功
- ✅ HTTP触发器已创建
- ✅ 镜像资源准备完成
- ✅ 函数已就绪

## 📋 测试步骤

### 步骤1：获取函数访问地址

#### 方法1：在触发器标签页查看

1. 点击顶部标签 **"触发器"**（Trigger）
2. 找到 **"defaultTrigger"**
3. 查看触发器的详细信息
4. 记录HTTP触发器的访问地址

**访问地址格式类似：**
```
https://manga-translator-xxxxx.cn-hangzhou.fcapp.run
```

#### 方法2：在函数拓扑图中查看

1. 在函数拓扑图中，找到 **"Trigger: defaultTrigger"**
2. 点击触发器
3. 查看触发器的详细信息
4. 记录HTTP触发器的访问地址

### 步骤2：测试函数

#### 测试1：健康检查

**使用curl命令：**
```bash
curl https://your-function-url/health
```

**预期响应：**
```json
{"status":"ok"}
```

**使用FC控制台测试：**
1. 点击顶部标签 **"测试"**（Test）
2. 选择 **"GET"** 方法
3. 路径填写：`/health`
4. 点击 **"测试"** 按钮

#### 测试2：根路径测试

**使用curl命令：**
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

#### 测试3：翻译功能测试

**使用curl命令：**
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

**使用FC控制台测试：**
1. 点击顶部标签 **"测试"**（Test）
2. 选择 **"POST"** 方法
3. 路径填写：`/translate`
4. 请求体填写：
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
5. 点击 **"测试"** 按钮

### 步骤3：查看日志

1. 点击顶部标签 **"日志"**（Log）
2. 查看函数执行日志
3. 检查是否有错误信息
4. 查看函数调用情况

### 步骤4：查看监控

1. 点击顶部标签 **"监控"**（Monitoring）
2. 查看函数调用次数
3. 查看执行时间
4. 查看错误率

## 🔍 测试检查清单

- [ ] 获取函数访问地址
- [ ] 健康检查测试（/health）
- [ ] 根路径测试（/）
- [ ] 翻译功能测试（/translate）
- [ ] 查看日志确认无错误
- [ ] 查看监控确认函数正常运行

## ⚠️ 常见问题

### 问题1：函数调用超时

**可能原因：**
- 翻译任务耗时过长
- 超时时间设置过短

**解决方法：**
1. 检查超时时间是否为600秒
2. 查看日志了解具体耗时
3. 优化翻译流程

### 问题2：函数返回错误

**可能原因：**
- 环境变量未设置
- 代码执行错误
- 镜像问题

**解决方法：**
1. 查看日志了解错误详情
2. 检查环境变量是否正确
3. 检查代码逻辑

### 问题3：无法访问函数

**可能原因：**
- 触发器配置错误
- 网络问题

**解决方法：**
1. 检查触发器配置
2. 检查访问地址是否正确
3. 检查网络连接

## 📝 下一步

测试成功后：
1. 记录函数访问地址
2. 集成到Kotlin后端服务
3. 更新Kotlin后端的配置，使用FC函数地址

## 🎉 恭喜！

函数已经准备完成，可以开始测试了！

