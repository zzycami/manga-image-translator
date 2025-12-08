# 本地开发计划

## 开发目标

在本地完整实现以下功能，然后再考虑部署到serverless：

1. ✅ Python翻译服务（已完成，运行在8000端口）
2. 🔨 Kotlin服务器（支付、进度管理、图片管理）
3. 🔨 网页前端（与Kotlin服务集成）
4. 🔨 数据库设计（PostgreSQL + Redis）

## 架构图

```
┌─────────────────┐
│   网页前端      │  (React/Vue + Kotlin API)
│  (localhost:3000)│
└────────┬────────┘
         │
┌────────▼────────┐
│  Kotlin服务端   │  (Spring Boot)
│ (localhost:8080)│
│                 │
│ - 用户认证      │
│ - 支付管理      │
│ - 任务管理      │
│ - 进度推送      │
│ - 图片上传/下载 │
└────────┬────────┘
         │
    ┌────┴────┬──────────────┐
    │         │              │
┌───▼───┐ ┌──▼────┐    ┌────▼────┐
│PostgreSQL│ │ Redis │    │Python翻译│
│         │ │       │    │服务      │
│ - 用户  │ │ - 队列│    │(8000端口)│
│ - 订单  │ │ - 缓存│    │          │
│ - 任务  │ │ - 进度│    │          │
└────────┘ └───────┘    └──────────┘
```

## 开发步骤

### 阶段1: 数据库和基础服务（1-2天）

#### 1.1 数据库初始化
```sql
-- 使用Docker快速启动
docker run -d --name postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=manga_translator \
  -p 5432:5432 \
  postgres:15

docker run -d --name redis \
  -p 6379:6379 \
  redis:7-alpine
```

#### 1.2 Kotlin项目初始化
```kotlin
// build.gradle.kts
dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.springframework.boot:spring-boot-starter-data-jpa")
    implementation("org.springframework.boot:spring-boot-starter-data-redis")
    implementation("org.springframework.boot:spring-boot-starter-websocket")
    implementation("org.postgresql:postgresql")
    implementation("com.fasterxml.jackson.module:jackson-module-kotlin")
    implementation("org.springframework.boot:spring-boot-starter-validation")
}
```

### 阶段2: 核心API接口（2-3天）

#### 2.1 任务管理API

**创建翻译任务**
```kotlin
POST /api/v1/translation/tasks
Content-Type: multipart/form-data

{
  "image": File,
  "config": {
    "translator": "deepseek",
    "target_lang": "CHS",
    "detection_size": 1536,
    ...
  }
}

Response:
{
  "task_id": "xxx",
  "status": "pending",
  "estimated_cost": 0.5,
  "queue_position": 0
}
```

**查询任务状态**
```kotlin
GET /api/v1/translation/tasks/{task_id}

Response:
{
  "task_id": "xxx",
  "status": "processing",
  "progress": {
    "current_step": "translating",
    "percentage": 75
  },
  "result_url": "http://...",
  "created_at": "2024-01-01T00:00:00Z"
}
```

**获取任务列表**
```kotlin
GET /api/v1/translation/tasks?page=1&size=20

Response:
{
  "tasks": [...],
  "total": 100,
  "page": 1
}
```

#### 2.2 支付API

**创建支付订单**
```kotlin
POST /api/v1/payment/orders
{
  "amount": 100.00,
  "currency": "CNY",
  "payment_method": "wechat" // 或 alipay, stripe
}

Response:
{
  "order_id": "xxx",
  "payment_url": "weixin://...",
  "qr_code": "data:image/png;base64,..."
}
```

**支付回调**
```kotlin
POST /api/v1/payment/callback/{provider}
// 处理微信/支付宝/Stripe的回调
```

**查询订单**
```kotlin
GET /api/v1/payment/orders/{order_id}
```

#### 2.3 用户积分API

**查询余额**
```kotlin
GET /api/v1/user/credits

Response:
{
  "credits": 150.50,
  "total_earned": 500.00,
  "total_spent": 349.50
}
```

**积分记录**
```kotlin
GET /api/v1/user/credits/transactions?page=1&size=20
```

### 阶段3: WebSocket进度推送（1天）

#### 3.1 WebSocket连接
```kotlin
// 客户端连接
ws://localhost:8080/ws/progress?token=xxx

// 服务端推送消息
{
  "type": "progress",
  "task_id": "xxx",
  "status": "translating",
  "percentage": 75,
  "current_step": "translating",
  "message": "正在翻译文本..."
}

{
  "type": "completed",
  "task_id": "xxx",
  "result_url": "http://..."
}

{
  "type": "error",
  "task_id": "xxx",
  "error": "翻译失败：API余额不足"
}
```

### 阶段4: Python服务集成（1-2天）

#### 4.1 调用Python翻译服务

```kotlin
@Service
class TranslationService(
    private val pythonApiClient: PythonApiClient
) {
    
    suspend fun startTranslation(
        taskId: String,
        imageUrl: String,
        config: TranslationConfig
    ) {
        // 调用Python服务的流式API
        pythonApiClient.translateStream(
            imageUrl = imageUrl,
            config = config,
            onProgress = { progress ->
                // 更新数据库
                updateTaskProgress(taskId, progress)
                // 推送WebSocket
                websocketService.sendProgress(taskId, progress)
            },
            onComplete = { resultUrl ->
                // 完成任务
                completeTask(taskId, resultUrl)
            },
            onError = { error ->
                // 处理错误
                failTask(taskId, error)
            }
        )
    }
}
```

#### 4.2 Python API客户端

```kotlin
@Component
class PythonApiClient(
    @Value("\${python.service.url:http://localhost:8000}") 
    private val baseUrl: String
) {
    private val client = HttpClient(CIO) {
        install(ContentNegotiation) {
            json()
        }
    }
    
    suspend fun translateStream(
        imageUrl: String,
        config: TranslationConfig,
        onProgress: (Progress) -> Unit,
        onComplete: (String) -> Unit,
        onError: (String) -> Unit
    ) {
        // 调用 /translate/with-form/image/stream/web 端点
        val response = client.post("$baseUrl/translate/with-form/image/stream/web") {
            contentType(ContentType.MultiPart.FormData)
            setBody(
                MultiPartFormDataContent(
                    formData {
                        append("image", File(imageUrl).readBytes())
                        append("config", config.toJson())
                    }
                )
            )
        }
        
        // 解析流式响应
        response.bodyAsChannel().consumeEach { byteBuffer ->
            // 解析进度更新
            // 格式: 1byte status + 4byte size + n byte data
            // status: 0=result, 1=progress, 2=error, 3=queue, 4=waiting
        }
    }
}
```

### 阶段5: 图片管理（1天）

#### 5.1 图片上传

```kotlin
POST /api/v1/files/upload
Content-Type: multipart/form-data

Response:
{
  "file_id": "xxx",
  "url": "http://localhost:8080/api/v1/files/{file_id}",
  "size": 1024000,
  "content_type": "image/png"
}
```

#### 5.2 图片存储策略

- **本地存储**: 开发环境使用本地文件系统
- **OSS存储**: 生产环境使用阿里云OSS/ AWS S3
- **结果图片**: 保存7天，自动清理

```kotlin
@Service
class FileService {
    private val uploadDir = Paths.get("./uploads")
    private val resultDir = Paths.get("./results")
    
    suspend fun saveUploadedFile(file: MultipartFile): FileInfo {
        val fileId = generateFileId()
        val filePath = uploadDir.resolve(fileId)
        file.transferTo(filePath.toFile())
        
        return FileInfo(
            fileId = fileId,
            url = "/api/v1/files/$fileId",
            size = file.size,
            contentType = file.contentType
        )
    }
    
    suspend fun saveResultFile(taskId: String, image: ByteArray): String {
        val fileId = generateFileId()
        val filePath = resultDir.resolve("$taskId/$fileId.png")
        Files.createDirectories(filePath.parent)
        Files.write(filePath, image)
        
        return "/api/v1/files/results/$taskId/$fileId.png"
    }
}
```

### 阶段6: 网页前端（2-3天）

#### 6.1 前端技术栈

```json
{
  "framework": "React + TypeScript",
  "ui": "Ant Design 或 Material-UI",
  "state": "React Query / SWR",
  "websocket": "socket.io-client",
  "http": "axios"
}
```

#### 6.2 核心页面

1. **翻译页面**
   - 图片上传
   - 配置选择
   - 实时进度显示
   - 结果预览和下载

2. **任务历史**
   - 任务列表
   - 状态筛选
   - 结果查看

3. **充值页面**
   - 选择金额
   - 支付二维码
   - 订单记录

4. **个人中心**
   - 积分余额
   - 消费记录
   - 设置

#### 6.3 前端集成示例

```typescript
// translation.service.ts
class TranslationService {
  private apiBase = 'http://localhost:8080/api/v1';
  private wsUrl = 'ws://localhost:8080/ws/progress';
  
  async createTask(image: File, config: TranslationConfig) {
    const formData = new FormData();
    formData.append('image', image);
    formData.append('config', JSON.stringify(config));
    
    const response = await axios.post(
      `${this.apiBase}/translation/tasks`,
      formData
    );
    
    return response.data;
  }
  
  connectWebSocket(taskId: string, callbacks: {
    onProgress: (progress: Progress) => void;
    onComplete: (resultUrl: string) => void;
    onError: (error: string) => void;
  }) {
    const ws = new WebSocket(`${this.wsUrl}?task_id=${taskId}`);
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'progress':
          callbacks.onProgress(data);
          break;
        case 'completed':
          callbacks.onComplete(data.result_url);
          break;
        case 'error':
          callbacks.onError(data.error);
          break;
      }
    };
    
    return ws;
  }
}
```

## 开发顺序建议

### Week 1: 基础搭建
- [ ] Day 1: 数据库设计和初始化
- [ ] Day 2: Kotlin项目搭建，基础实体类
- [ ] Day 3: 任务管理API（创建、查询）
- [ ] Day 4: Python服务集成（调用翻译API）
- [ ] Day 5: WebSocket进度推送

### Week 2: 完整功能
- [ ] Day 1: 支付系统（创建订单、回调处理）
- [ ] Day 2: 积分系统（充值、消费、记录）
- [ ] Day 3: 图片管理（上传、存储、下载）
- [ ] Day 4-5: 前端开发（翻译页面、任务历史）

### Week 3: 完善和测试
- [ ] Day 1-2: 前端完善（充值页面、个人中心）
- [ ] Day 3: 集成测试
- [ ] Day 4: 性能优化
- [ ] Day 5: 文档和部署准备

## 本地开发环境配置

### docker-compose.yml
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: manga_translator
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  
  # Python翻译服务（已运行）
  # python-service:
  #   build: .
  #   ports:
  #     - "8000:8000"

volumes:
  postgres_data:
```

### application.yml (Kotlin)
```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/manga_translator
    username: postgres
    password: password
  
  redis:
    host: localhost
    port: 6379
  
  servlet:
    multipart:
      max-file-size: 50MB
      max-request-size: 50MB

python:
  service:
    url: http://localhost:8000

file:
  upload-dir: ./uploads
  result-dir: ./results
  max-age-days: 7
```

## 测试计划

### API测试
- Postman集合测试所有API
- 单元测试核心业务逻辑
- 集成测试完整流程

### 前端测试
- 组件测试
- E2E测试（Playwright/Cypress）

### 性能测试
- 并发翻译任务测试
- WebSocket连接数测试
- 数据库查询性能

## 下一步

完成本地开发后，可以考虑：
1. 容器化部署（Docker）
2. 迁移到Serverless（逐步迁移）
3. 生产环境优化（CDN、缓存、监控）


