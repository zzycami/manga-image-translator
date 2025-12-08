# FC GPU 部署实时步骤指导

## 当前状态
✅ 已登录阿里云控制台

## 第一步：开通服务（2分钟）

### 1.1 开通函数计算服务（FC）
1. 访问：https://fcnext.console.aliyun.com/
2. 如果未开通，点击"立即开通"（免费）
3. 选择区域：**华东1（杭州）** - `cn-hangzhou`（推荐）

### 1.2 注册 Docker Hub 账号（如果没有）
1. 访问：https://hub.docker.com/
2. 点击"Sign Up"注册账号（免费）
3. 验证邮箱
4. 记住您的用户名（稍后会用到）

**说明**：我们使用 Docker Hub 替代 ACR，完全免费，无需付费。

### 1.2 开通函数计算服务（FC）
1. 访问：https://fcnext.console.aliyun.com/
2. 如果未开通，点击"立即开通"（免费）
3. 选择区域：**华东1（杭州）** - `cn-hangzhou`（推荐）

---

## 第二步：创建 ACR 仓库（5分钟）

### 2.1 创建命名空间
1. 在 ACR 控制台，点击左侧"命名空间"
2. 点击"创建命名空间"
3. 命名空间名称：`manga-translator`（或您喜欢的名称）
4. 类型：选择"私有"
5. 点击"确定"

### 2.2 创建镜像仓库
1. 点击左侧"镜像仓库"
2. 点击"创建镜像仓库"
3. 配置：
   - **命名空间**：选择刚才创建的 `manga-translator`
   - **仓库名称**：`manga-image-translator`
   - **仓库类型**：选择"私有"
   - **代码源**：选择"本地仓库"
   - **摘要**：漫画翻译服务镜像
4. 点击"下一步" → "创建镜像仓库"

### 2.3 获取登录信息
1. 在仓库详情页，点击"访问凭证"标签
2. 记录以下信息（稍后会用到）：
   - **公网地址**：`registry.cn-hangzhou.aliyuncs.com`
   - **登录命令**：类似 `docker login --username=xxx registry.cn-hangzhou.aliyuncs.com`
   - **用户名**：通常是您的阿里云账号
   - **密码**：点击"设置密码"设置一个密码（记住它！）

---

## 第三步：构建和推送镜像（20-40分钟）

### 3.1 在本地终端执行

打开终端，执行以下命令：

```bash
# 1. 进入项目目录
cd /Users/zhouzeyong/Documents/GitHub/manga-image-translator

# 2. 构建镜像（需要 10-20 分钟，取决于网络速度）
docker build -f Dockerfile.fc -t manga-image-translator:fc .
```

**注意**：构建过程可能需要较长时间，请耐心等待。

### 3.2 标记镜像

构建完成后，执行（替换为您的实际 ACR 地址）：

```bash
# 替换 registry.cn-hangzhou.aliyuncs.com/manga-translator 为您的实际地址
docker tag manga-image-translator:fc \
  registry.cn-hangzhou.aliyuncs.com/manga-translator/manga-image-translator:fc
```

### 3.3 登录 ACR

```bash
# 替换为您的实际信息
docker login --username=您的用户名 registry.cn-hangzhou.aliyuncs.com
# 输入刚才设置的密码
```

### 3.4 推送镜像

```bash
# 推送镜像（需要 10-30 分钟，取决于镜像大小和网络速度）
docker push registry.cn-hangzhou.aliyuncs.com/manga-translator/manga-image-translator:fc
```

**提示**：推送过程可能需要较长时间，可以先去控制台做其他配置。

---

## 第四步：创建函数计算服务（2分钟）

1. 访问：https://fcnext.console.aliyun.com/
2. 确保选择区域：**华东1（杭州）**
3. 点击左侧"服务及函数"
4. 点击"创建服务"
5. 配置：
   - **服务名称**：`manga-translator`
   - **描述**：漫画翻译服务
   - 其他保持默认
6. 点击"确定"

---

## 第四步：创建函数（10分钟）

### 4.1 进入创建函数页面
1. 在服务列表中，点击刚才创建的 `manga-translator` 服务
2. 点击"创建函数"

### 4.2 选择创建方式
选择 **"使用自定义运行时创建"**

### 4.3 配置函数基本信息
- **函数名称**：`translate`
- **运行环境**：选择 **"Custom Container"**
- **镜像地址**：输入您的 Docker Hub 镜像地址
  ```
  docker.io/your-dockerhub-username/manga-image-translator:fc
  ```
  
  **示例**：
  ```
  docker.io/zhouzeyong/manga-image-translator:fc
  ```
  
  **重要**：
  - 必须包含 `docker.io/` 前缀
  - 替换 `your-dockerhub-username` 为您的实际 Docker Hub 用户名

### 4.4 配置函数规格（重要！）

**实例类型**：
- 选择 **"GPU 实例"** ⚠️ 重要！

**资源配置**：
- **内存规格**：`8192` MB（8GB）
- **GPU 显存**：`16384` MB（16GB）⚠️ 重要！
- **超时时间**：`600` 秒（10分钟）
- **vCPU**：会自动分配（GPU 实例通常 4 核）

### 4.5 配置环境变量

点击"环境变量"，添加以下变量：

| 变量名 | 变量值 |
|--------|--------|
| `PYTHONUNBUFFERED` | `1` |
| `DEEPSEEK_API_KEY` | `sk-fa51105a356949fa91dc262b7eea2aa6` |
| `DEEPSEEK_API_BASE` | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | `deepseek-chat` |

### 4.6 创建函数
1. 检查所有配置无误
2. 点击"创建"

**注意**：
- 如果镜像还在推送中，创建可能会失败，等镜像推送完成后再创建
- Docker Hub 在国内访问可能较慢，首次拉取镜像可能需要较长时间

---

## 第五步：创建 HTTP 触发器（2分钟）

1. 在函数详情页，点击"触发器"标签
2. 点击"创建触发器"
3. 配置：
   - **触发器类型**：选择 **"HTTP 触发器"**
   - **触发方式**：选择 **"匿名访问"**（测试用）
   - **请求方法**：勾选 `GET` 和 `POST`
   - **认证方式**：选择 **"anonymous"**
4. 点击"创建"

### 5.1 获取函数 URL

创建触发器后，会显示函数 URL，格式类似：
```
https://manga-translator-translate.cn-hangzhou.fcapp.run
```

**记录这个 URL**，稍后测试会用到！

---

## 第六步：测试部署（5分钟）

### 6.1 健康检查

在终端执行（替换为您的函数 URL）：

```bash
curl https://manga-translator-translate.cn-hangzhou.fcapp.run/health
```

预期响应：
```json
{"status":"ok"}
```

### 6.2 测试队列查询

```bash
curl https://manga-translator-translate.cn-hangzhou.fcapp.run/queue-size
```

预期响应：`0`（队列为空）

### 6.3 测试翻译（可选）

准备一张测试图片 `test.jpg`，然后：

```bash
curl -X POST https://manga-translator-translate.cn-hangzhou.fcapp.run/translate/with-form/image/stream \
  -F "image=@test.jpg" \
  -F 'config={"translator":{"translator":"deepseek","target_lang":"CHS"}}' \
  --output result.png
```

**注意**：
- 首次调用会较慢（冷启动 + Docker Hub 拉取镜像）
- 可能需要 5-10 分钟
- 这是正常的，后续调用会快很多

---

## 常见问题

### Q1: 镜像推送很慢？
**A**: 这是正常的，镜像可能几GB大小，需要 10-30 分钟。可以先去控制台配置其他内容。

### Q2: 创建函数时提示镜像不存在？
**A**: 等待镜像推送完成后再创建。可以在 ACR 控制台查看推送进度。

### Q3: GPU 不可用？
**A**: 
- 确认选择了"GPU 实例"类型
- 确认 GPU 显存设置为 16384 MB
- 查看函数日志确认 GPU 是否被正确识别

### Q4: 函数超时？
**A**: 
- 首次调用会较慢（冷启动）
- 可以增加超时时间到 900 秒
- 查看日志了解具体卡在哪一步

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

---

## 检查清单

- [ ] ACR 服务已开通
- [ ] FC 服务已开通
- [ ] ACR 命名空间已创建
- [ ] ACR 镜像仓库已创建
- [ ] 镜像已构建
- [ ] 镜像已推送到 ACR
- [ ] FC 服务已创建
- [ ] 函数已创建（GPU 实例）
- [ ] HTTP 触发器已创建
- [ ] 环境变量已配置
- [ ] 健康检查通过

