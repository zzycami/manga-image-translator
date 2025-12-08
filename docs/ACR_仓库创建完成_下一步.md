# ACR 仓库创建完成 - 下一步操作

## 当前状态
✅ ACR 仓库已创建成功

## 从页面信息中获取的关键信息

- **仓库名称**：`manga-image-translator`
- **命名空间**：`manga-translator`
- **登录地址**：`manga-translator-registry.cn-hangzhou.cr.aliyuncs.com`
- **用户名**：`zzycami@foxmail.com`
- **完整镜像地址**：`manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc`

---

## 第一步：开启公网访问（如果需要）（2分钟）

**注意**：页面显示"请先开启访问控制的网络入口"

1. 在 ACR 控制台，找到 **"访问控制"** 或 **"网络设置"** 菜单
2. 开启 **"公网访问"** 或 **"公网入口"**
3. 确认公网地址已启用

**如果找不到设置入口**：
- 可以先尝试直接登录，如果失败再回来开启
- 或者查看 ACR 控制台的"访问控制"或"网络"相关设置

---

## 第二步：设置登录密码（如果还没有）（1分钟）

1. 在 ACR 控制台，找到 **"访问凭证"** 或 **"密码管理"**
2. 设置一个密码（记住它！）
3. 或者使用开通服务时设置的密码

---

## 第三步：在本地构建镜像（10-20分钟）

打开终端，执行：

```bash
# 1. 进入项目目录
cd /Users/zhouzeyong/Documents/GitHub/manga-image-translator

# 2. 构建镜像（需要 10-20 分钟）
docker build -f Dockerfile.fc -t manga-image-translator:fc .
```

**注意**：构建过程可能需要较长时间，请耐心等待。

---

## 第四步：标记镜像（1分钟）

构建完成后，执行：

```bash
# 标记镜像（使用您的实际地址）
docker tag manga-image-translator:fc \
  manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc
```

---

## 第五步：登录 ACR（1分钟）

```bash
# 登录 ACR（使用您的用户名）
docker login --username=zzycami@foxmail.com manga-translator-registry.cn-hangzhou.cr.aliyuncs.com
# 输入您的密码
```

---

## 第六步：推送镜像到 ACR（10-30分钟）

```bash
# 推送镜像（需要 10-30 分钟，取决于镜像大小和网络速度）
docker push manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc
```

**注意**：
- 推送过程可能需要较长时间，请耐心等待
- 镜像可能几GB大小，这是正常的
- 推送完成后，可以在 ACR 控制台看到镜像

---

## 完整镜像地址（用于 FC 配置）

在后续创建 FC 函数时，使用以下镜像地址：

```
manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc
```

---

## 快速命令汇总

```bash
# 1. 构建镜像
cd /Users/zhouzeyong/Documents/GitHub/manga-image-translator
docker build -f Dockerfile.fc -t manga-image-translator:fc .

# 2. 标记镜像
docker tag manga-image-translator:fc \
  manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc

# 3. 登录 ACR
docker login --username=zzycami@foxmail.com manga-translator-registry.cn-hangzhou.cr.aliyuncs.com

# 4. 推送镜像
docker push manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc
```

---

## 完成以上步骤后

完成以上步骤后，告诉我：
1. ✅ 公网访问是否已开启
2. ✅ 镜像是否已构建完成
3. ✅ 镜像是否已推送到 ACR

我会继续指导您在 FC 中创建函数。

