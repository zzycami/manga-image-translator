# FC端口和路由说明

## 🔍 端口处理方式

### 本地运行 vs FC环境

#### 本地运行（server/main.py）

在本地运行时，`server/main.py` 运行在**一个端口**（默认8000），同时提供：
- Web UI界面（`/`）
- API接口（`/translate`, `/health` 等）

**所有功能都在同一个FastAPI应用中，通过不同的路径（路由）区分。**

#### FC环境（fc_server.py）

在FC环境中，也是**一个端口**（9000），所有请求都通过同一个FastAPI应用处理：
- Web UI界面（`/`）
- API接口（`/translate`, `/health` 等）

**同样通过路径（路由）来区分不同的功能。**

## 📋 路由设计

### FC环境中的路由

所有请求都通过**同一个端口（9000）**，通过**不同的路径**来区分：

```
https://manga-tanslator-pssdhxnbcm.cn-hangzhou.fcapp.run/
├── /                          → Web UI界面（HTML）
├── /api                       → API信息（JSON）
├── /health                    → 健康检查（API）
├── /status                    → 服务状态（API）
├── /translate                 → 翻译接口（API）
├── /translate/with-form/image/stream → 流式翻译接口（API）
├── /results/list              → 结果列表（API）
├── /results/clear             → 清空缓存（API）
├── /results/{folder_name}     → 删除结果（API）
└── /result/...                → 静态文件服务
```

### 如何区分Web和API？

**通过Content-Type和路径：**

1. **Web UI界面**
   - 路径：`/`
   - Content-Type：`text/html`
   - 返回：HTML页面

2. **API接口**
   - 路径：`/health`, `/translate` 等
   - Content-Type：`application/json` 或 `application/octet-stream`
   - 返回：JSON数据或二进制流

## 🔧 FC的端口配置

### Dockerfile配置

```dockerfile
CMD ["gunicorn", "fc_server:app", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:9000", "--timeout", "600"]
```

- **监听端口**：9000
- **绑定地址**：0.0.0.0（所有网络接口）

### FC函数配置

- **监听端口**：9000（必须与Dockerfile中的端口一致）
- **HTTP触发器**：将外部请求路由到容器内的9000端口

## 💡 为什么不需要多个端口？

### 1. FastAPI的路由系统

FastAPI通过**路径（路由）**来区分不同的功能，不需要多个端口：

```python
@app.get("/")                    # Web UI
@app.get("/health")              # API
@app.post("/translate")          # API
```

### 2. FC的HTTP触发器

FC的HTTP触发器会将所有请求路由到容器的9000端口，然后由FastAPI应用根据路径分发到不同的处理函数。

### 3. 统一管理

使用一个端口的好处：
- ✅ 简化配置
- ✅ 统一管理
- ✅ 减少资源占用
- ✅ 更容易部署

## 📊 请求流程

```
用户请求
    ↓
FC HTTP触发器
    ↓
容器端口 9000
    ↓
gunicorn + FastAPI
    ↓
根据路径路由到不同的处理函数
    ├── / → Web UI界面
    ├── /health → 健康检查
    ├── /translate → 翻译接口
    └── ...
```

## 🎯 总结

**在FC环境中：**
- ✅ **只有一个端口**：9000
- ✅ **通过路径区分**：Web UI和API使用不同的路径
- ✅ **统一管理**：所有功能都在同一个FastAPI应用中

**不需要多个端口，通过路由（路径）来区分不同的功能即可！**

