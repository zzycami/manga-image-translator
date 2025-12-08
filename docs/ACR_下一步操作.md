# ACR 实例启动后的操作步骤

## 当前状态
✅ ACR 企业版已购买，实例正在启动中

## 第一步：等待实例启动完成（2-5分钟）

1. 在 ACR 控制台查看实例状态
2. 等待状态变为 **"运行中"**
3. 通常需要 2-5 分钟

---

## 第二步：创建命名空间（2分钟）

1. 在 ACR 控制台，点击左侧 **"命名空间"**
2. 点击 **"创建命名空间"**
3. 配置：
   - **命名空间名称**：`manga-translator`（或您喜欢的名称）
   - **类型**：选择 **"私有"**
   - **描述**：漫画翻译服务（可选）
4. 点击 **"确定"**

---

## 第三步：创建镜像仓库（3分钟）

1. 在 ACR 控制台，点击左侧 **"镜像仓库"**
2. 点击 **"创建镜像仓库"**
3. 配置：
   - **命名空间**：选择刚才创建的 `manga-translator`
   - **仓库名称**：`manga-image-translator`
   - **仓库类型**：选择 **"私有"**
   - **代码源**：选择 **"本地仓库"**
   - **摘要**：漫画翻译服务镜像（可选）
4. 点击 **"下一步"** → **"创建镜像仓库"**

---

## 第四步：获取登录信息（2分钟）

1. 在仓库详情页，点击 **"访问凭证"** 标签
2. 记录以下信息（稍后会用到）：

   **公网地址**（类似）：
   ```
   registry.cn-hangzhou.aliyuncs.com
   ```
   
   **完整镜像地址**（格式）：
   ```
   registry.cn-hangzhou.aliyuncs.com/manga-translator/manga-image-translator:fc
   ```
   
   **登录命令**（类似）：
   ```bash
   docker login --username=your-username registry.cn-hangzhou.aliyuncs.com
   ```
   
   **用户名**：
   - 通常是您的阿里云账号
   - 或者您在 ACR 中设置的用户名
   
   **密码**：
   - 点击 **"设置密码"** 设置一个密码
   - **记住这个密码！**（稍后登录会用到）

---

## 第五步：在本地构建镜像（10-20分钟）

打开终端，执行以下命令：

```bash
# 1. 进入项目目录
cd /Users/zhouzeyong/Documents/GitHub/manga-image-translator

# 2. 构建镜像（需要 10-20 分钟，取决于网络速度）
docker build -f Dockerfile.fc -t manga-image-translator:fc .
```

**注意**：
- 构建过程可能需要较长时间，请耐心等待
- 如果网络较慢，可能需要更长时间
- 构建过程中会下载很多依赖，这是正常的

---

## 第六步：标记镜像（1分钟）

构建完成后，执行（替换为您的实际 ACR 地址）：

```bash
# 替换为您的实际地址
docker tag manga-image-translator:fc \
  registry.cn-hangzhou.aliyuncs.com/manga-translator/manga-image-translator:fc
```

**注意**：
- 替换 `registry.cn-hangzhou.aliyuncs.com` 为您的实际公网地址
- 替换 `manga-translator` 为您的实际命名空间名称
- 替换 `manga-image-translator` 为您的实际仓库名称

---

## 第七步：登录 ACR（1分钟）

```bash
# 替换为您的实际信息
docker login --username=您的用户名 registry.cn-hangzhou.aliyuncs.com
# 输入刚才设置的密码
```

---

## 第八步：推送镜像到 ACR（10-30分钟）

```bash
# 推送镜像（需要 10-30 分钟，取决于镜像大小和网络速度）
docker push registry.cn-hangzhou.aliyuncs.com/manga-translator/manga-image-translator:fc
```

**注意**：
- 推送过程可能需要较长时间，请耐心等待
- 镜像可能几GB大小，这是正常的
- 推送完成后，可以在 ACR 控制台看到镜像

---

## 完成以上步骤后

完成以上步骤后，告诉我：
1. ✅ 命名空间是否已创建
2. ✅ 镜像仓库是否已创建
3. ✅ 镜像是否已构建完成
4. ✅ 镜像是否已推送到 ACR
5. ✅ 您的完整镜像地址（格式：`registry.cn-hangzhou.aliyuncs.com/命名空间/仓库名:fc`）

我会继续指导您在 FC 中创建函数。

---

## 快速检查清单

- [ ] ACR 实例已启动（状态：运行中）
- [ ] 命名空间已创建
- [ ] 镜像仓库已创建
- [ ] 已获取登录信息（地址、用户名、密码）
- [ ] 镜像已构建
- [ ] 镜像已标记
- [ ] 已登录 ACR
- [ ] 镜像已推送

