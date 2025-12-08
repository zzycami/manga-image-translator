# 推送镜像到 ACR - 完整步骤

## 您的 ACR 信息

- **公网地址**：`manga-translator-registry.cn-hangzhou.cr.aliyuncs.com`
- **命名空间**：`manga-translator`
- **仓库名称**：`manga-image-translator`
- **完整镜像地址**：`manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc`
- **用户名**：`zzycami@foxmail.com`

---

## 完整操作步骤

### 步骤1：构建镜像（正在执行中...）

```bash
cd /Users/zhouzeyong/Documents/GitHub/manga-image-translator
docker build -f Dockerfile.fc -t manga-image-translator:fc .
```

**预计时间**：10-20 分钟

**注意**：构建过程可能需要较长时间，请耐心等待。

---

### 步骤2：标记镜像

构建完成后，执行：

```bash
docker tag manga-image-translator:fc \
  manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc
```

---

### 步骤3：登录 ACR

```bash
docker login --username=zzycami@foxmail.com manga-translator-registry.cn-hangzhou.cr.aliyuncs.com
```

然后输入您的 ACR 密码。

---

### 步骤4：推送镜像

```bash
docker push manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc
```

**预计时间**：10-30 分钟（取决于镜像大小和网络速度）

---

## 一键执行脚本

我已经为您创建了自动化脚本，构建完成后可以直接运行：

```bash
# 使用脚本（会自动执行标记、登录、推送）
./push_to_acr.sh
```

或者手动执行上述步骤 2-4。

---

## 镜像地址（用于 FC 配置）

在后续创建 FC 函数时，使用以下镜像地址：

```
manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc
```

---

## 检查构建进度

构建过程中，您可以在终端看到进度。构建完成后，告诉我，我们继续下一步。

