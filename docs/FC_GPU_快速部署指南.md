# FC GPU 快速部署指南（早期验证）

## 部署复杂度：⭐⭐⭐（中等）

**总体评估**：部署不算太复杂，主要是镜像构建和配置，大约需要 30-60 分钟。

## 前置准备（5分钟）

### 1. 阿里云账号准备
- ✅ 注册并实名认证阿里云账号
- ✅ 开通函数计算服务（FC）
- ✅ 开通容器镜像服务（ACR）
- ✅ 获取 AccessKey ID 和 Secret（在控制台 -> 访问控制 -> 用户）

### 2. 本地环境准备
```bash
# 确保已安装 Docker
docker --version

# 如果没有，安装 Docker Desktop（macOS）
# brew install --cask docker
```

## 部署方式选择

### 方式1：控制台部署（推荐新手）⭐⭐⭐⭐⭐

**优点**：可视化操作，简单直观，适合第一次部署  
**时间**：约 30 分钟

### 方式2：命令行部署（推荐有经验）⭐⭐⭐⭐

**优点**：自动化，可重复，适合后续更新  
**时间**：约 20 分钟

---

## 方式1：控制台部署（详细步骤）

### 步骤1：构建并推送 Docker 镜像（10分钟）

#### 1.1 构建镜像
```bash
cd /Users/zhouzeyong/Documents/GitHub/manga-image-translator

# 构建镜像（可能需要 10-20 分钟，取决于网络速度）
docker build -f Dockerfile.fc -t manga-image-translator:fc .
```

#### 1.2 登录阿里云容器镜像服务
1. 访问 [容器镜像服务控制台](https://cr.console.aliyun.com/)
2. 创建命名空间（如：`manga-translator`）
3. 创建镜像仓库（如：`manga-image-translator`），选择"本地仓库"
4. 获取登录命令（在仓库详情页 -> 访问凭证）

#### 1.3 推送镜像
```bash
# 登录 ACR（替换为您的实际地址）
docker login --username=your-username registry.cn-hangzhou.aliyuncs.com
# 输入密码（在控制台获取）

# 标记镜像（替换为您的实际地址）
docker tag manga-image-translator:fc \
  registry.cn-hangzhou.aliyuncs.com/manga-translator/manga-image-translator:fc

# 推送镜像（可能需要 10-30 分钟，取决于镜像大小）
docker push registry.cn-hangzhou.aliyuncs.com/manga-translator/manga-image-translator:fc
```

### 步骤2：创建函数计算服务（5分钟）

1. 访问 [函数计算控制台](https://fcnext.console.aliyun.com/)
2. 选择区域（推荐：`cn-hangzhou` 华东1）
3. 点击"创建服务"
   - 服务名称：`manga-translator`
   - 描述：漫画翻译服务
   - 其他保持默认

### 步骤3：创建函数（10分钟）

1. 在服务中点击"创建函数"
2. 选择"使用自定义运行时创建"
3. 配置函数：

   **基本信息**：
   - 函数名称：`translate`
   - 运行环境：**Custom Container**
   - 镜像地址：`registry.cn-hangzhou.aliyuncs.com/manga-translator/manga-image-translator:fc`

   **资源配置**（重要！）：
   - **内存规格**：8192 MB（8GB）
   - **超时时间**：600 秒（10分钟）
   - **实例类型**：选择 **GPU 实例**
   - **GPU 显存**：16384 MB（16GB）
   - **vCPU**：4核（GPU 实例自动分配）

   **环境变量**：
   ```
   PYTHONUNBUFFERED=1
   DEEPSEEK_API_KEY=sk-fa51105a356949fa91dc262b7eea2aa6
   DEEPSEEK_API_BASE=https://api.deepseek.com
   DEEPSEEK_MODEL=deepseek-chat
   ```

4. 点击"创建"

### 步骤4：创建 HTTP 触发器（2分钟）

1. 在函数详情页，点击"触发器"标签
2. 点击"创建触发器"
3. 配置：
   - 触发器类型：**HTTP 触发器**
   - 触发方式：**匿名访问**（测试用，生产环境建议配置认证）
   - 请求方法：GET, POST
4. 点击"创建"

### 步骤5：获取访问地址（1分钟）

创建触发器后，会显示函数 URL，格式：
```
https://manga-translator-translate.cn-hangzhou.fcapp.run
```

---

## 方式2：命令行部署（自动化）

### 快速部署脚本

我已经为您准备了自动化脚本，只需修改配置即可：

```bash
# 1. 修改部署脚本配置
vim fc_deploy_simple.sh

# 2. 设置以下变量：
# - ACR_REGISTRY: 您的 ACR 地址
# - ACR_USERNAME: ACR 用户名
# - ACR_PASSWORD: ACR 密码（或使用环境变量）

# 3. 运行部署脚本
chmod +x fc_deploy_simple.sh
./fc_deploy_simple.sh
```

### 使用 Fun 工具（推荐）

```bash
# 1. 安装 Fun 工具
npm install @alicloud/fun -g

# 2. 配置 Fun
fun config
# 输入 AccessKey ID 和 Secret
# 选择区域：cn-hangzhou

# 3. 修改 fc_config.yaml
# - 更新 image 地址
# - 更新 region
# - 设置环境变量

# 4. 部署
fun deploy
```

---

## 验证部署（5分钟）

### 1. 健康检查
```bash
# 替换为您的函数 URL
curl https://manga-translator-translate.cn-hangzhou.fcapp.run/health
```

预期响应：
```json
{"status": "ok"}
```

### 2. 测试翻译（简单）
```bash
curl -X POST https://manga-translator-translate.cn-hangzhou.fcapp.run/queue-size
```

预期响应：`0`（队列为空）

### 3. 测试翻译（完整）

准备一张测试图片，然后：

```bash
curl -X POST https://manga-translator-translate.cn-hangzhou.fcapp.run/translate/with-form/image/stream \
  -F "image=@test.jpg" \
  -F 'config={"translator":{"translator":"deepseek","target_lang":"CHS"}}' \
  --output result.png
```

**注意**：
- 首次调用会较慢（冷启动，需要加载模型）
- 可能需要 2-5 分钟
- 后续调用会快很多（实例已预热）

---

## 常见问题

### Q1: 镜像构建失败？
**A**: 检查网络连接，可能需要配置代理或使用国内镜像源

### Q2: 推送镜像很慢？
**A**: 镜像可能较大（几GB），这是正常的，耐心等待

### Q3: GPU 不可用？
**A**: 
- 确认选择了"GPU 实例"类型
- 确认 GPU 显存设置为 16384 MB
- 查看函数日志确认 GPU 是否被正确识别

### Q4: 函数超时？
**A**: 
- 首次调用会较慢（冷启动）
- 可以增加超时时间到 900 秒（15分钟）
- 查看日志了解具体卡在哪一步

### Q5: 内存不足？
**A**: 
- 增加内存到 16384 MB（16GB）
- 检查模型文件是否过大
- 考虑使用 NAS 存储模型

---

## 成本估算（早期验证）

### GPU 实例成本
- **单次调用**：约 ¥0.11（60秒执行时间）
- **100次调用**：约 ¥11
- **免费额度**：每月 15 万 CU
  - GPU 任务：约 104 次调用（每次 60 秒）
  - 建议先用免费额度测试

### 成本控制建议
1. ✅ 先用免费额度测试（15 万 CU）
2. ✅ 设置预算告警（在云监控中配置）
3. ✅ 测试完成后及时删除函数（避免意外调用）

---

## 下一步

部署成功后：

1. **集成到 Kotlin 后端**
   - 修改 `LocalMangaTranslationProvider` 中的服务地址
   - 测试调用流程

2. **监控和优化**
   - 查看函数日志
   - 监控执行时间和成本
   - 优化配置

3. **生产环境准备**
   - 配置认证（HTTP 触发器）
   - 设置预留实例（减少冷启动）
   - 配置 NAS 存储模型（如果镜像太大）

---

## 快速检查清单

部署前：
- [ ] 阿里云账号已实名认证
- [ ] 已开通 FC 和 ACR 服务
- [ ] 已获取 AccessKey
- [ ] 本地已安装 Docker

部署中：
- [ ] 镜像构建成功
- [ ] 镜像已推送到 ACR
- [ ] 函数已创建（GPU 实例）
- [ ] HTTP 触发器已创建
- [ ] 环境变量已配置

部署后：
- [ ] 健康检查通过
- [ ] 测试翻译成功
- [ ] 查看日志确认 GPU 可用

---

## 总结

**部署复杂度**：⭐⭐⭐（中等）  
**预计时间**：30-60 分钟  
**主要步骤**：构建镜像 → 推送镜像 → 创建函数 → 创建触发器 → 测试

**推荐**：第一次部署使用控制台方式，更直观；后续更新使用命令行方式，更高效。

