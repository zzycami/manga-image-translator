# Serverless AI翻译服务架构方案

## 整体架构图

```
┌─────────────────┐
│  Kotlin服务端   │  (业务逻辑层、API网关)
│  (Spring Boot)  │
└────────┬────────┘
         │
    ┌────┴────┬──────────────┬──────────────┐
    │         │              │              │
┌───▼───┐ ┌──▼────┐    ┌────▼────┐   ┌────▼────┐
│ 数据库 │ │ 消息队列│    │ 对象存储 │   │ 支付系统 │
│(PostgreSQL│ │(Redis/│    │(OSS/S3) │   │(Stripe/│
│ 或MongoDB)│ │RabbitMQ)│   │         │   │ 微信/支付宝)│
└────────┘ └────────┘    └─────────┘   └─────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
            ┌───────▼──────┐   ┌────────▼────────┐
            │ Serverless   │   │  进度推送服务    │
            │ AI函数       │   │ (WebSocket/SSE) │
            │ (Lambda/FC)  │   │                 │
            └──────────────┘   └─────────────────┘
```

## 1. 数据库设计

### 1.1 推荐方案：PostgreSQL + Redis

**PostgreSQL (主数据库)**
- 用户数据、订单、任务记录等持久化数据
- 支持JSON字段存储配置信息
- 支持全文搜索

**Redis (缓存/队列)**
- 任务队列
- 进度状态缓存
- 用户会话
- 限流计数

### 1.2 数据表设计

```sql
-- 用户表
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(64) UNIQUE NOT NULL,  -- 业务用户ID
    email VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 订单表
CREATE TABLE orders (
    id BIGSERIAL PRIMARY KEY,
    order_id VARCHAR(64) UNIQUE NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'CNY',
    status VARCHAR(20) NOT NULL,  -- pending, paid, failed, refunded
    payment_method VARCHAR(50),
    payment_id VARCHAR(128),  -- 第三方支付ID
    created_at TIMESTAMP DEFAULT NOW(),
    paid_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- 翻译任务表
CREATE TABLE translation_tasks (
    id BIGSERIAL PRIMARY KEY,
    task_id VARCHAR(64) UNIQUE NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    order_id VARCHAR(64),  -- 关联订单（付费任务）
    status VARCHAR(20) NOT NULL,  -- pending, processing, completed, failed
    progress JSONB,  -- 存储进度信息
    config JSONB NOT NULL,  -- 翻译配置
    source_url TEXT,  -- 源图片URL
    result_url TEXT,  -- 结果图片URL
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- 用户余额/积分表
CREATE TABLE user_credits (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(64) UNIQUE NOT NULL,
    credits DECIMAL(10, 2) DEFAULT 0,  -- 积分余额
    total_earned DECIMAL(10, 2) DEFAULT 0,
    total_spent DECIMAL(10, 2) DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- 积分交易记录
CREATE TABLE credit_transactions (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    task_id VARCHAR(64),
    order_id VARCHAR(64),
    amount DECIMAL(10, 2) NOT NULL,  -- 正数为获得，负数为消费
    type VARCHAR(20) NOT NULL,  -- charge, consume, refund
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- 创建索引
CREATE INDEX idx_tasks_user_id ON translation_tasks(user_id);
CREATE INDEX idx_tasks_status ON translation_tasks(status);
CREATE INDEX idx_tasks_created_at ON translation_tasks(created_at DESC);
CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_status ON orders(status);
```

## 2. Serverless AI服务部署

### 2.1 推荐平台选择

**国内：**
- 阿里云函数计算 (FC) - 支持GPU，按量计费
- 腾讯云SCF - 支持GPU
- 百度云CFC

**国外：**
- AWS Lambda (需要容器镜像，支持GPU)
- Google Cloud Functions
- Azure Functions

### 2.2 函数设计

```python
# serverless_function.py
import json
import os
from manga_translator import MangaTranslator, Config

def handler(event, context):
    """
    Serverless函数入口
    event: {
        "task_id": "xxx",
        "image_url": "https://...",
        "config": {...},
        "callback_url": "https://your-api.com/callback"
    }
    """
    task_id = event['task_id']
    image_url = event['image_url']
    config_dict = event['config']
    callback_url = event.get('callback_url')
    
    # 初始化翻译器
    config = Config(**config_dict)
    translator = MangaTranslator(config)
    
    # 下载图片
    import requests
    response = requests.get(image_url)
    image = Image.open(BytesIO(response.content))
    
    # 执行翻译（同步或异步）
    result = translator.translate(image)
    
    # 上传结果到OSS
    result_url = upload_to_oss(result, task_id)
    
    # 回调通知Kotlin服务
    if callback_url:
        requests.post(callback_url, json={
            "task_id": task_id,
            "status": "completed",
            "result_url": result_url
        })
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "task_id": task_id,
            "result_url": result_url
        })
    }
```

### 2.3 进度推送方案

**方案A: WebSocket (推荐)**
- Kotlin服务端维护WebSocket连接
- Serverless函数通过回调更新进度
- 实时推送进度给客户端

**方案B: Server-Sent Events (SSE)**
- 更简单，单向推送
- 适合进度更新场景

**方案C: 轮询**
- 客户端定期查询任务状态
- 实现简单但不够实时

## 3. Kotlin服务端设计

### 3.1 技术栈建议

```kotlin
// Spring Boot 3.x
dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.springframework.boot:spring-boot-starter-data-jpa")
    implementation("org.springframework.boot:spring-boot-starter-data-redis")
    implementation("org.springframework.boot:spring-boot-starter-websocket")
    implementation("org.postgresql:postgresql")
    implementation("com.fasterxml.jackson.module:jackson-module-kotlin")
}
```

### 3.2 核心服务设计

```kotlin
// TranslationService.kt
@Service
class TranslationService(
    private val taskRepository: TaskRepository,
    private val redisTemplate: RedisTemplate<String, String>,
    private val serverlessClient: ServerlessClient,
    private val ossService: OSSService
) {
    
    suspend fun createTranslationTask(
        userId: String,
        image: MultipartFile,
        config: TranslationConfig
    ): TranslationTask {
        // 1. 上传图片到OSS
        val imageUrl = ossService.uploadImage(image, userId)
        
        // 2. 创建任务记录
        val task = TranslationTask(
            taskId = generateTaskId(),
            userId = userId,
            status = TaskStatus.PENDING,
            sourceUrl = imageUrl,
            config = config
        )
        taskRepository.save(task)
        
        // 3. 检查用户余额
        val credits = creditService.getUserCredits(userId)
        val cost = calculateCost(config)
        if (credits < cost) {
            throw InsufficientCreditsException()
        }
        
        // 4. 扣费
        creditService.consumeCredits(userId, cost, task.taskId)
        
        // 5. 提交到Serverless函数
        serverlessClient.invokeAsync(
            functionName = "manga-translator",
            payload = mapOf(
                "task_id" to task.taskId,
                "image_url" to imageUrl,
                "config" to config.toMap(),
                "callback_url" to "${apiBaseUrl}/api/tasks/${task.taskId}/callback"
            )
        )
        
        // 6. 更新任务状态
        task.status = TaskStatus.PROCESSING
        taskRepository.save(task)
        
        // 7. 设置Redis进度缓存
        redisTemplate.opsForValue().set(
            "task:progress:${task.taskId}",
            "pending",
            Duration.ofHours(1)
        )
        
        return task
    }
    
    suspend fun updateTaskProgress(
        taskId: String,
        progress: TaskProgress
    ) {
        // 1. 更新数据库
        val task = taskRepository.findByTaskId(taskId)
            ?: throw TaskNotFoundException()
        
        task.progress = progress
        taskRepository.save(task)
        
        // 2. 更新Redis缓存
        redisTemplate.opsForValue().set(
            "task:progress:${taskId}",
            progress.status,
            Duration.ofHours(1)
        )
        
        // 3. 通过WebSocket推送进度
        websocketService.sendProgress(task.userId, taskId, progress)
    }
    
    suspend fun completeTask(
        taskId: String,
        resultUrl: String
    ) {
        val task = taskRepository.findByTaskId(taskId)
            ?: throw TaskNotFoundException()
        
        task.status = TaskStatus.COMPLETED
        task.resultUrl = resultUrl
        task.completedAt = Instant.now()
        taskRepository.save(task)
        
        // 清理Redis缓存
        redisTemplate.delete("task:progress:$taskId")
        
        // 通知用户
        websocketService.sendCompletion(task.userId, taskId, resultUrl)
    }
}
```

### 3.3 WebSocket进度推送

```kotlin
@Component
class TranslationWebSocketHandler : TextWebSocketHandler() {
    
    private val sessions = ConcurrentHashMap<String, MutableSet<WebSocketSession>>()
    
    override fun afterConnectionEstablished(session: WebSocketSession) {
        val userId = getUserIdFromSession(session)
        sessions.computeIfAbsent(userId) { mutableSetOf() }.add(session)
    }
    
    fun sendProgress(userId: String, taskId: String, progress: TaskProgress) {
        sessions[userId]?.forEach { session ->
            if (session.isOpen) {
                session.sendMessage(TextMessage(
                    jsonMapper.writeValueAsString(mapOf(
                        "type" to "progress",
                        "task_id" to taskId,
                        "status" to progress.status,
                        "percentage" to progress.percentage
                    ))
                ))
            }
        }
    }
}
```

## 4. 支付管理

### 4.1 支付流程

```
用户发起支付
    ↓
Kotlin服务创建订单
    ↓
调用支付网关(Stripe/微信/支付宝)
    ↓
用户完成支付
    ↓
支付网关回调通知
    ↓
Kotlin服务验证并充值积分
    ↓
更新订单状态
```

### 4.2 支付服务设计

```kotlin
@Service
class PaymentService(
    private val orderRepository: OrderRepository,
    private val creditService: CreditService,
    private val stripeClient: StripeClient  // 或微信/支付宝客户端
) {
    
    suspend fun createPaymentOrder(
        userId: String,
        amount: BigDecimal,
        currency: String = "CNY"
    ): PaymentOrder {
        // 1. 创建订单
        val order = Order(
            orderId = generateOrderId(),
            userId = userId,
            amount = amount,
            currency = currency,
            status = OrderStatus.PENDING
        )
        orderRepository.save(order)
        
        // 2. 调用支付网关创建支付
        val paymentIntent = stripeClient.createPaymentIntent(
            amount = (amount * 100).toInt(),  // 转换为分
            currency = currency.lowercase(),
            metadata = mapOf("order_id" to order.orderId)
        )
        
        // 3. 保存支付ID
        order.paymentId = paymentIntent.id
        orderRepository.save(order)
        
        return PaymentOrder(
            orderId = order.orderId,
            clientSecret = paymentIntent.clientSecret
        )
    }
    
    @Transactional
    suspend fun handlePaymentCallback(
        paymentId: String,
        status: String
    ) {
        val order = orderRepository.findByPaymentId(paymentId)
            ?: throw OrderNotFoundException()
        
        if (order.status != OrderStatus.PENDING) {
            return  // 已处理过
        }
        
        when (status) {
            "succeeded" -> {
                // 支付成功，充值积分
                val credits = order.amount * 10  // 1元 = 10积分
                creditService.addCredits(
                    userId = order.userId,
                    amount = credits,
                    orderId = order.orderId,
                    description = "充值"
                )
                
                order.status = OrderStatus.PAID
                order.paidAt = Instant.now()
            }
            "failed" -> {
                order.status = OrderStatus.FAILED
            }
        }
        
        orderRepository.save(order)
    }
}
```

## 5. 成本计算

```kotlin
@Service
class PricingService {
    
    fun calculateCost(config: TranslationConfig): BigDecimal {
        var baseCost = BigDecimal("0.1")  // 基础费用
        
        // 根据配置调整价格
        when (config.detectionResolution) {
            "2048" -> baseCost += BigDecimal("0.05")
            "2560" -> baseCost += BigDecimal("0.1")
        }
        
        when (config.translator) {
            "deepseek", "openai" -> baseCost += BigDecimal("0.2")  // API费用
            "offline" -> baseCost += BigDecimal("0.05")  // 计算资源费用
        }
        
        if (config.upscaleRatio != null) {
            baseCost += BigDecimal("0.1")  // 超分费用
        }
        
        return baseCost
    }
}
```

## 6. 部署建议

### 6.1 环境变量配置

```yaml
# application.yml
spring:
  datasource:
    url: jdbc:postgresql://${DB_HOST}:5432/manga_translator
    username: ${DB_USER}
    password: ${DB_PASSWORD}
  
  redis:
    host: ${REDIS_HOST}
    port: 6379
    password: ${REDIS_PASSWORD}

serverless:
  provider: aliyun  # 或 aws, tencent
  function-name: manga-translator
  access-key: ${SERVERLESS_ACCESS_KEY}
  secret-key: ${SERVERLESS_SECRET_KEY}

oss:
  provider: aliyun  # 或 aws-s3
  endpoint: ${OSS_ENDPOINT}
  bucket: ${OSS_BUCKET}
  access-key: ${OSS_ACCESS_KEY}
  secret-key: ${OSS_SECRET_KEY}

payment:
  stripe:
    secret-key: ${STRIPE_SECRET_KEY}
    webhook-secret: ${STRIPE_WEBHOOK_SECRET}
  # 或微信/支付宝配置
```

### 6.2 监控和日志

- **APM**: 使用Elastic APM或SkyWalking监控性能
- **日志**: 集中式日志收集(ELK Stack)
- **告警**: 任务失败率、支付异常等关键指标

## 7. 安全考虑

1. **API认证**: JWT Token或OAuth2
2. **限流**: Redis实现用户级别限流
3. **图片验证**: 文件类型、大小限制
4. **支付安全**: 支付回调签名验证
5. **数据加密**: 敏感数据加密存储

## 8. 扩展性考虑

1. **水平扩展**: Kotlin服务无状态，可多实例部署
2. **队列削峰**: 使用消息队列缓冲请求
3. **CDN加速**: 结果图片通过CDN分发
4. **缓存策略**: 热门图片结果缓存

## 9. 成本优化

1. **Serverless按需计费**: 只在有任务时计费
2. **结果存储**: 设置过期时间自动清理
3. **批量处理**: 支持批量翻译降低单次成本
4. **资源池化**: 预热常用模型减少冷启动


