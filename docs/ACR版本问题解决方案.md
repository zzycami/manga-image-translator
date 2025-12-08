# ACR版本问题解决方案

## 问题描述

FC的GPU函数不支持经济版ACR实例，提示：
> "manga-translator 不支持实例规格为经济版的实例"

## 解决方案

### 方案1：升级ACR到企业版（推荐）

**优点：**
- ✅ 功能完整
- ✅ 支持所有FC功能
- ✅ 性能更好

**操作步骤：**
1. 登录阿里云控制台
2. 进入 **容器镜像服务（ACR）**
3. 找到您的ACR实例：`manga-translator-registry`
4. 点击 **升级** 或 **变更规格**
5. 选择 **企业版**（或 **个人版**）
6. 确认升级（可能需要付费）

**注意：**
- 企业版需要付费
- 个人版可能免费或费用较低
- 升级后需要重新推送镜像

### 方案2：使用Docker Hub（临时方案）

**优点：**
- ✅ 免费
- ✅ 无需升级ACR
- ✅ 可以立即使用

**缺点：**
- ❌ 在中国大陆访问可能较慢
- ❌ 需要将镜像推送到Docker Hub

**操作步骤：**

#### 步骤1：推送镜像到Docker Hub

```bash
# 登录Docker Hub
docker login

# 标记镜像
docker tag manga-image-translator:fc-optimized your-dockerhub-username/manga-image-translator:fc

# 推送镜像
docker push your-dockerhub-username/manga-image-translator:fc
```

#### 步骤2：在FC中选择"使用自定义仓库中的镜像"

1. 在FC函数配置页面
2. 选择 **"使用自定义仓库中的镜像"**
3. 填写Docker Hub镜像地址：
   ```
   your-dockerhub-username/manga-image-translator:fc
   ```
4. 如果需要认证，填写Docker Hub的用户名和密码

### 方案3：创建新的企业版ACR实例

**操作步骤：**
1. 登录阿里云控制台
2. 进入 **容器镜像服务（ACR）**
3. 创建新实例，选择 **企业版**
4. 创建命名空间和仓库
5. 重新推送镜像到新实例

## 推荐方案

### 如果预算允许：方案1（升级ACR到企业版）

**原因：**
- 功能完整
- 性能更好
- 长期使用更稳定

### 如果预算有限：方案2（使用Docker Hub）

**原因：**
- 免费
- 可以立即使用
- 适合测试和验证

## 快速操作指南

### 如果选择升级ACR：

1. 登录阿里云控制台
2. 进入ACR服务
3. 找到实例：`manga-translator-registry`
4. 点击 **升级** → 选择 **企业版** 或 **个人版**
5. 确认升级
6. 升级完成后，在FC中重新选择镜像

### 如果选择使用Docker Hub：

1. 推送镜像到Docker Hub（见上方命令）
2. 在FC函数配置中，选择 **"使用自定义仓库中的镜像"**
3. 填写Docker Hub镜像地址
4. 继续配置其他项

## 注意事项

1. **ACR版本限制**：FC的GPU函数确实不支持经济版ACR
2. **镜像地址**：升级或切换后，镜像地址会变化，需要更新
3. **成本考虑**：企业版ACR需要付费，个人版可能免费
4. **网络速度**：Docker Hub在中国大陆可能较慢，建议配置镜像加速器

## 下一步

选择方案后，告诉我您的选择，我可以帮您：
- 升级ACR的详细步骤
- 推送镜像到Docker Hub的命令
- 在FC中配置自定义镜像仓库的方法

