# FC镜像Tag注意事项

## 提示说明

### 1. HTTP Server实现 ✅

**提示：** "您需要在容器中实现一个 HTTP Server"

**我们的实现：**
- ✅ 已经实现：`fc_server.py` 使用 FastAPI 实现了 HTTP Server
- ✅ 监听端口：9000
- ✅ 使用 gunicorn 运行，支持多进程
- ✅ 已经配置在镜像的CMD中

**无需担心，我们已经满足要求！**

### 2. 镜像Tag和Digest ⚠️ **重要**

**提示：** "函数计算将使用您创建或更新函数时镜像 Tag 所应对的 Digest，请确保不要重复推送覆盖此 Tag 为其他 Digest，否则函数将会调用失败。"

**这是什么意思？**

- FC会记录创建函数时镜像Tag对应的Digest（镜像的唯一标识）
- 如果后续推送新镜像时使用相同的Tag，但Digest不同，FC不会自动更新
- 这可能导致函数调用失败或使用旧版本镜像

**解决方案：**

#### 方案1：使用版本Tag（推荐）

推送新镜像时，使用新的Tag：
```bash
# 第一次推送
docker push manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc

# 更新镜像时，使用新Tag
docker push manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc-v2
docker push manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc-v3
```

然后在FC中更新函数配置，使用新的Tag。

#### 方案2：更新函数配置

如果必须使用相同Tag，需要：
1. 推送新镜像（使用相同Tag）
2. 在FC函数配置中，手动触发更新
3. 或者删除并重新创建函数

#### 方案3：使用latest Tag（不推荐）

使用 `latest` Tag，但每次更新后需要在FC中手动更新函数配置。

**最佳实践：**
- ✅ 使用版本Tag（如：`fc-v1`, `fc-v2`）
- ✅ 更新时推送新Tag
- ✅ 在FC中更新函数配置使用新Tag
- ❌ 避免重复推送覆盖相同Tag

### 3. 个人版ACR限制（不适用）

**提示：** "阿里云镜像仓库个人版面向个人开发者，公测限额免费使用，无SLA承诺及SLA受损赔偿且有使用限制。"

**说明：**
- 您已经升级到企业版ACR，不受此限制
- 企业版有SLA承诺和更好的服务保障
- 可以忽略此提示

## 当前状态检查

### ✅ 已满足的要求

1. ✅ **HTTP Server已实现**：`fc_server.py` + FastAPI + gunicorn
2. ✅ **监听端口已配置**：9000
3. ✅ **镜像已推送**：使用Tag `fc`
4. ✅ **ACR版本**：企业版（不受个人版限制）

### ⚠️ 需要注意的事项

1. ⚠️ **Tag管理**：后续更新镜像时，建议使用新Tag（如 `fc-v2`）
2. ⚠️ **函数更新**：如果更新镜像，需要在FC中更新函数配置

## 后续镜像更新流程

### 当需要更新镜像时：

```bash
# 1. 构建新镜像
docker build --platform linux/amd64 -f Dockerfile.fc.optimized -t manga-image-translator:fc-optimized .

# 2. 标记为新版本Tag
docker tag manga-image-translator:fc-optimized \
  manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc-v2

# 3. 推送新Tag
docker push manga-translator-registry.cn-hangzhou.cr.aliyuncs.com/manga-translator/manga-image-translator:fc-v2

# 4. 在FC函数配置中，更新镜像地址为新Tag
```

## 总结

- ✅ **HTTP Server**：已实现，无需担心
- ⚠️ **Tag管理**：注意不要重复推送覆盖相同Tag，建议使用版本Tag
- ✅ **ACR版本**：企业版，不受个人版限制

**当前可以继续配置，这些提示只是提醒，不影响创建函数！**

