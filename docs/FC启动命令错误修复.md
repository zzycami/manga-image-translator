# FC启动命令错误修复

## 错误原因

**错误信息：**
```
Function instance exited unexpectedly(code 2, message:no such file or directory) 
with start command 'python -m manga_translator gunicorn fc_server:app ...'
```

**问题分析：**
- 官方镜像的ENTRYPOINT是：`["python", "-m", "manga_translator"]`
- FC添加的启动命令是：`gunicorn fc_server:app ...`
- 实际执行的命令变成了：`python -m manga_translator gunicorn fc_server:app ...`
- 这是错误的！`manga_translator` 不接受 `gunicorn` 作为参数

## 解决方案

### 方案1：在FC中覆盖启动命令（推荐）

#### 步骤1：修改函数配置

1. 在FC函数详情页面
2. 点击 **"配置"**（Configuration）标签
3. 找到 **"启动命令"**（Startup Command）配置
4. 填写完整的启动命令：

```
gunicorn fc_server:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:9000 --timeout 600
```

**重要：** 必须填写完整的命令，覆盖镜像的默认ENTRYPOINT

#### 步骤2：保存配置

1. 点击 **"保存"** 或 **"更新"**
2. 等待配置生效

#### 步骤3：重新测试

1. 点击 **"测试"** 标签
2. 重新测试函数

### 方案2：修改Dockerfile（如果方案1不行）

如果方案1不行，需要修改Dockerfile，改变ENTRYPOINT：

#### 修改 Dockerfile.fc.optimized

```dockerfile
FROM zyddnys/manga-image-translator:main

WORKDIR /app

# 复制 FC 专用的 HTTP 服务器文件
COPY fc_server.py /app/fc_server.py

# 安装FC HTTP服务器依赖
RUN pip install mangum uvicorn gunicorn --no-cache-dir

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 创建必要的目录
RUN mkdir -p /tmp /app/result && chmod 1777 /tmp

# 覆盖ENTRYPOINT，使用空ENTRYPOINT，让CMD生效
ENTRYPOINT []

# FC入口点
CMD ["gunicorn", "fc_server:app", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:9000", "--timeout", "600"]
```

然后重新构建和推送镜像。

## 推荐操作步骤

### 步骤1：在FC中修改启动命令

1. 在FC函数详情页面
2. 点击 **"配置"**（Configuration）标签
3. 找到 **"启动命令"**（Startup Command）
4. 填写：
   ```
   gunicorn fc_server:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:9000 --timeout 600
   ```
5. 点击 **"保存"** 或 **"更新"**

### 步骤2：重新测试

1. 等待配置生效
2. 点击 **"测试"** 标签
3. 重新测试函数

## 启动命令说明

**正确的启动命令：**
```
gunicorn fc_server:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:9000 --timeout 600
```

**参数说明：**
- `gunicorn`：WSGI HTTP服务器
- `fc_server:app`：FastAPI应用
- `-k uvicorn.workers.UvicornWorker`：使用Uvicorn worker
- `-b 0.0.0.0:9000`：绑定到9000端口
- `--timeout 600`：超时时间600秒

## 注意事项

1. **启动命令必须完整**
   - 不能只写 `gunicorn`
   - 必须包含所有参数

2. **覆盖镜像的ENTRYPOINT**
   - FC的启动命令会覆盖镜像的ENTRYPOINT
   - 确保启动命令正确

3. **监听端口必须匹配**
   - 启动命令中的端口（9000）必须与FC配置的监听端口一致

## 下一步

1. **修改启动命令**（在FC函数配置中）
2. **保存配置**
3. **重新测试函数**

