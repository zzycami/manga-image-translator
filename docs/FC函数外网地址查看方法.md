# FC函数外网地址查看方法

## 查看方法

### 方法1：在触发器标签页查看（推荐）

#### 步骤1：进入触发器页面

1. 在函数详情页面
2. 点击顶部标签栏的 **"触发器"**（Trigger）标签
3. 进入触发器列表页面

#### 步骤2：查看触发器详情

1. 找到 **"defaultTrigger"** 或您创建的HTTP触发器
2. 点击触发器名称或详情
3. 查看触发器的详细信息
4. 找到 **"公网访问地址"** 或 **"访问地址"**

**地址格式类似：**
```
https://manga-translator-xxxxx.cn-hangzhou.fcapp.run
```

### 方法2：在函数拓扑图中查看

1. 在函数详情页面
2. 找到函数拓扑图
3. 点击 **"Trigger: defaultTrigger"**
4. 查看触发器的详细信息
5. 找到访问地址

### 方法3：在函数列表页面查看

1. 返回函数列表页面
2. 找到您的函数：`manga-translator`
3. 在函数列表中，可能有访问地址列
4. 或点击函数名称进入详情，再查看触发器

## 详细操作步骤

### 步骤1：点击"触发器"标签

1. 在函数详情页面顶部
2. 找到并点击 **"触发器"**（Trigger）标签

### 步骤2：查看触发器列表

1. 应该能看到 **"defaultTrigger"** 或您创建的HTTP触发器
2. 触发器类型应该是 **"HTTP触发器"**

### 步骤3：查看访问地址

1. 点击触发器名称或详情
2. 在触发器详情中，找到：
   - **"公网访问地址"**
   - **"访问地址"**
   - **"URL"**
   - 或类似的字段

**地址格式：**
```
https://manga-translator-xxxxx.cn-hangzhou.fcapp.run
```

## 如果找不到访问地址

### 可能的原因

1. **触发器未创建**
   - 需要先创建HTTP触发器

2. **触发器类型不对**
   - 需要是HTTP触发器
   - 其他类型的触发器可能没有外网地址

3. **触发器配置问题**
   - 检查触发器配置是否正确

### 解决方法

1. **检查触发器是否存在**
   - 在触发器标签页查看
   - 如果没有，需要创建HTTP触发器

2. **创建HTTP触发器**
   - 点击 **"创建触发器"** 按钮
   - 选择 **"HTTP触发器"**
   - 配置触发器
   - 创建后会显示访问地址

## 使用访问地址

获取访问地址后，可以使用以下方式测试：

### 使用curl命令

```bash
# 健康检查
curl https://your-function-url/health

# 根路径
curl https://your-function-url/

# 翻译功能
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

### 在浏览器中访问

直接在浏览器中访问：
```
https://your-function-url/health
```

## 快速操作

1. **点击"触发器"标签**
2. **找到HTTP触发器（defaultTrigger）**
3. **查看访问地址**
4. **复制地址用于测试**

## 下一步

获取访问地址后，可以使用curl命令或浏览器测试函数。

