# FC更新镜像步骤

## ✅ 镜像推送成功！

镜像已成功推送到ACR：
- **镜像地址**：`manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc-v3`
- **Digest**：`sha256:2804ced4a57b93f1ce7bf53abf82886f2a1006a99f26578cf2d62a1297e1fb79`

## 📋 在FC中更新镜像

### 步骤1：进入函数配置页面

1. 登录阿里云控制台
2. 进入 **函数计算（FC）** 服务
3. 找到函数：`manga-translator`
4. 点击函数名称进入详情页面
5. 点击顶部标签 **"配置"**（Configuration）

### 步骤2：修改镜像地址

1. 找到 **"修改镜像"** 或 **"镜像地址"** 配置项
2. 更新镜像地址为：
   ```
   manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc-v3
   ```
3. 或者只更新Tag为：`fc-v3`（如果基础地址已经正确）

### 步骤3：保存配置

1. 点击 **"保存"** 或 **"更新"** 按钮
2. 等待配置生效（可能需要几分钟）

### 步骤4：等待镜像更新

- 等待几分钟让新镜像生效
- 可以在函数详情页面查看更新状态

## 🧪 测试新功能

### 测试1：Web UI界面

访问：
```
https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run/
```

应该能看到Web管理界面，包括：
- ✅ 服务状态
- ✅ API端点列表
- ✅ 缓存管理功能

### 测试2：状态接口

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

### 测试3：结果列表

```bash
curl https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run/results/list
```

**预期响应：**
```json
{
  "directories": []
}
```

### 测试4：流式翻译（Kotlin后端）

Kotlin后端会自动使用新的流式翻译接口。

## 🎉 新功能列表

更新后的FC函数支持：

1. **流式翻译接口** ✅
   - `/translate/with-form/image/stream` - 兼容Kotlin后端
   - 支持进度报告
   - 支持错误处理

2. **Web UI管理界面** ✅
   - `/` - Web管理界面
   - 查看服务状态
   - 管理缓存文件
   - 删除结果文件

3. **状态和缓存管理** ✅
   - `/status` - 获取服务状态
   - `/queue-size` - 获取队列大小（返回0）
   - `/results/list` - 列出结果
   - `/results/clear` - 清空缓存
   - `/results/{folder_name}` - 删除指定结果

4. **静态文件服务** ✅
   - `/result` - 静态文件服务

## 📝 注意事项

1. **镜像更新**：更新镜像后，需要等待几分钟生效
2. **缓存文件**：FC环境使用 `/tmp/result` 目录，容器重启后会丢失
3. **Web UI**：可以通过浏览器访问管理界面

## 下一步

1. ✅ 在FC中更新镜像Tag为 `fc-v3`
2. ✅ 等待镜像更新生效
3. ✅ 测试Web UI界面
4. ✅ 测试流式翻译功能
5. ✅ 使用Kotlin后端调用翻译服务

