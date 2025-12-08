# FC GPU 部署步骤（使用 Docker Hub，无需 ACR）

## 前置准备

✅ 已登录阿里云控制台  
✅ 无需开通 ACR（使用 Docker Hub 替代）

---

## 第一步：开通函数计算服务（FC）（2分钟）

1. 访问：https://fcnext.console.aliyun.com/
2. 如果未开通，点击"立即开通"（免费）
3. 选择区域：**华东1（杭州）** - `cn-hangzhou`（推荐）

---

## 第二步：注册 Docker Hub 账号（如果没有）（2分钟）

1. 访问：https://hub.docker.com/
2. 点击"Sign Up"注册账号（免费）
3. 验证邮箱
4. 记住您的用户名（稍后会用到）

---

## 第三步：构建和推送镜像到 Docker Hub（20-40分钟）

### 3.1 在本地终端执行

打开终端，执行以下命令：

```bash
# 1. 进入项目目录
cd /Users/zhouzeyong/Documents/GitHub/manga-image-translator

# 2. 构建镜像（需要 10-20 分钟）
docker build -f Dockerfile.fc -t manga-image-translator:fc .
```

### 3.2 登录 Docker Hub

```bash
# 登录 Docker Hub（输入您的用户名和密码）
docker login
# 输入您的 Docker Hub 用户名
# 输入您的 Docker Hub 密码
```

### 3.3 标记镜像

```bash
# 替换 your-dockerhub-username 为您的 Docker Hub 用户名
docker tag manga-image-translator:fc your-dockerhub-username/manga-image-translator:fc
```

**示例**：
```bash
# 如果您的 Docker Hub 用户名是 zhouzeyong
docker tag manga-image-translator:fc zhouzeyong/manga-image-translator:fc
```

### 3.4 推送镜像到 Docker Hub

```bash
# 推送镜像（需要 10-30 分钟，取决于镜像大小和网络速度）
docker push your-dockerhub-username/manga-image-translator:fc
```

**注意**：
- 首次推送可能需要较长时间
- 如果网络较慢，可以考虑使用代理或镜像加速器
- 推送完成后，镜像会显示在您的 Docker Hub 仓库中

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

## 第五步：创建函数（10分钟）

### 5.1 进入创建函数页面
1. 在服务列表中，点击刚才创建的 `manga-translator` 服务
2. 点击"创建函数"

### 5.2 选择创建方式
选择 **"使用自定义运行时创建"**

### 5.3 配置函数基本信息
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
  
  **注意**：
  - 必须包含 `docker.io/` 前缀
  - 替换 `your-dockerhub-username` 为您的实际用户名

### 5.4 配置函数规格（重要！）

**实例类型**：
- 选择 **"GPU 实例"** ⚠️ 重要！

**资源配置**：
- **内存规格**：`8192` MB（8GB）
- **GPU 显存**：`16384` MB（16GB）⚠️ 重要！
- **超时时间**：`600` 秒（10分钟）
- **vCPU**：会自动分配（GPU 实例通常 4 核）

### 5.5 配置环境变量

点击"环境变量"，添加以下变量：

| 变量名 | 变量值 |
|--------|--------|
| `PYTHONUNBUFFERED` | `1` |
| `DEEPSEEK_API_KEY` | `sk-fa51105a356949fa91dc262b7eea2aa6` |
| `DEEPSEEK_API_BASE` | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | `deepseek-chat` |

### 5.6 创建函数
1. 检查所有配置无误
2. 点击"创建"

**注意**：
- 如果镜像还在推送中，创建可能会失败，等镜像推送完成后再创建
- Docker Hub 在国内访问可能较慢，首次拉取镜像可能需要较长时间

---

## 第六步：创建 HTTP 触发器（2分钟）

1. 在函数详情页，点击"触发器"标签
2. 点击"创建触发器"
3. 配置：
   - **触发器类型**：选择 **"HTTP 触发器"**
   - **触发方式**：选择 **"匿名访问"**（测试用）
   - **请求方法**：勾选 `GET` 和 `POST`
   - **认证方式**：选择 **"anonymous"**
4. 点击"创建"

### 6.1 获取函数 URL

创建触发器后，会显示函数 URL，格式类似：
```
https://manga-translator-translate.cn-hangzhou.fcapp.run
```

**记录这个 URL**，稍后测试会用到！

---

## 第七步：测试部署（5分钟）

### 7.1 健康检查

在终端执行（替换为您的函数 URL）：

```bash
curl https://manga-translator-translate.cn-hangzhou.fcapp.run/health
```

预期响应：
```json
{"status":"ok"}
```

### 7.2 测试队列查询

```bash
curl https://manga-translator-translate.cn-hangzhou.fcapp.run/queue-size
```

预期响应：`0`（队列为空）

### 7.3 测试翻译（可选）

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

## Docker Hub 使用注意事项

### 1. 镜像地址格式
- ✅ 正确：`docker.io/username/repository:tag`
- ❌ 错误：`username/repository:tag`（缺少 docker.io 前缀）

### 2. 访问速度
- Docker Hub 在国内访问可能较慢
- 首次拉取镜像可能需要较长时间
- 可以考虑使用镜像加速器（但 FC 内部拉取可能无法加速）

### 3. 免费限制
- 公开仓库：免费
- 私有仓库：需要付费（$5/月）
- 拉取限制：每月 200 次（6 小时内的重复拉取不计）

### 4. 安全性
- 公开仓库：任何人都可以拉取
- 如果包含敏感信息，建议使用私有仓库或 ACR

---

## 常见问题

### Q1: 镜像推送很慢？
**A**: 
- Docker Hub 在国内访问可能较慢
- 可以考虑使用代理或镜像加速器
- 或者选择在非高峰时段推送

### Q2: 创建函数时提示镜像不存在？
**A**: 
- 等待镜像推送完成后再创建
- 可以在 Docker Hub 网站查看镜像是否已上传
- 确认镜像地址格式正确（包含 `docker.io/` 前缀）

### Q3: 函数启动很慢？
**A**: 
- 首次启动需要从 Docker Hub 拉取镜像，可能需要 5-10 分钟
- 这是正常的，后续调用会快很多
- 可以考虑使用预留实例减少冷启动

### Q4: GPU 不可用？
**A**: 
- 确认选择了"GPU 实例"类型
- 确认 GPU 显存设置为 16384 MB
- 查看函数日志确认 GPU 是否被正确识别

---

## 成本对比

### Docker Hub
- **镜像存储**：免费（公开仓库）
- **拉取次数**：每月 200 次免费（通常足够使用）
- **总成本**：¥0

### ACR 企业版
- **费用**：约 ¥500+/月
- **优点**：国内访问快，支持私有仓库

**结论**：早期验证阶段，使用 Docker Hub 完全免费，推荐！

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

3. **如果后续需要**
   - 如果访问速度成为问题，可以考虑升级到 ACR
   - 或者使用其他容器镜像仓库

---

## 检查清单

- [ ] Docker Hub 账号已注册
- [ ] 镜像已构建
- [ ] 镜像已推送到 Docker Hub
- [ ] FC 服务已开通
- [ ] FC 服务已创建
- [ ] 函数已创建（GPU 实例，镜像地址使用 Docker Hub）
- [ ] HTTP 触发器已创建
- [ ] 环境变量已配置
- [ ] 健康检查通过

