# FC修改认证方式为匿名访问

## 当前问题

**错误信息：**
```json
{
  "Code": "MissingRequiredHeader",
  "Message": "required HTTP header Date was not specified"
}
```

**原因：**
- 触发器配置了 **"签名认证"**
- 需要HTTP请求签名才能访问
- 直接访问会失败

## 解决方案：修改为匿名访问

### 步骤1：进入触发器详情

1. 在函数详情页面
2. 点击 **"触发器"**（Trigger）标签
3. 找到 **"defaultTrigger"** 或您的HTTP触发器

### 步骤2：编辑触发器

1. 点击触发器右侧的 **"编辑"** 按钮
2. 进入触发器编辑页面

### 步骤3：修改认证方式

1. 找到 **"认证方式"** 配置项
2. 将 **"签名认证"** 改为 **"匿名访问"**
3. 保存配置

### 步骤4：等待配置生效

1. 配置保存后，等待几秒钟
2. 配置生效后，可以匿名访问

## 修改后的测试

修改为匿名访问后，可以使用以下命令测试：

### 健康检查

```bash
curl https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run/health
```

**预期响应：**
```json
{"status":"ok"}
```

### 根路径

```bash
curl https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run/
```

### 翻译功能

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

2. **使用curl命令测试**（推荐）

## 注意事项

1. **匿名访问的安全性**：
   - 匿名访问意味着任何人都可以调用函数
   - 测试环境可以使用
   - 生产环境建议使用签名认证或绑定自定义域名

2. **生产环境建议**：
   - 使用签名认证
   - 或绑定自定义域名
   - 或使用ALB、API网关等产品

## 下一步

1. **修改认证方式为匿名访问**
2. **使用curl测试 `/health` 接口**
3. **确认函数正常工作**

