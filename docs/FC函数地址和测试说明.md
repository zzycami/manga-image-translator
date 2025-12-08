# FC函数地址和测试说明

## ✅ 函数访问地址

**公网访问地址：**
```
https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run
```

**内网访问地址：**
```
https://manga-tanslator-pssdhxnbcm.cn-hangzhou-vpc.fcapp.run
```

## 关于"强制下载"的问题

### 为什么会强制下载？

在浏览器中直接访问函数地址时，可能会强制下载文件，这是因为：

1. **浏览器行为**：某些浏览器对某些响应类型会触发下载
2. **Content-Type**：如果响应头设置不当，浏览器可能认为这是文件下载
3. **根路径行为**：直接访问根路径 `/` 时，某些配置可能导致下载

### 解决方法

**不要直接在浏览器中访问根地址**，而是：

1. **访问 `/health` 路径**：
   ```
   https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run/health
   ```

2. **使用curl命令测试**（推荐）：
   ```bash
   curl https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run/health
   ```

## 测试命令

### 1. 健康检查测试

```bash
curl https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run/health
```

**预期响应：**
```json
{"status":"ok"}
```

### 2. 根路径测试

```bash
curl https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run/
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

### 3. 翻译功能测试

```bash
curl -X POST https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run/translate \
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

## 关于认证方式

**当前配置：签名认证**

这意味着：
- 直接访问可能需要签名
- 但 `/health` 和 `/` 路径通常可以匿名访问
- 如果无法访问，可能需要配置为"匿名访问"

### 修改认证方式（如果需要）

1. 在触发器详情页面
2. 点击 **"编辑"** 按钮
3. 修改 **"认证方式"** 为 **"匿名访问"**
4. 保存配置

## 注意事项

1. **生产环境警告**：
   - FC提示不要在生产环境使用默认公网域名
   - 生产环境建议绑定自定义域名或使用ALB、API网关

2. **内网访问**：
   - 内网地址只能在VPC内访问
   - 公网地址可以在任何地方访问

3. **签名认证**：
   - 当前是签名认证
   - 如果测试时无法访问，可以改为匿名访问

## 下一步

1. **使用curl测试 `/health` 接口**
2. **如果返回 `{"status":"ok"}`，说明函数正常**
3. **如果需要，修改认证方式为匿名访问**

