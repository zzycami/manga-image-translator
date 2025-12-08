# 阿里云函数计算（FC）资源与计费详解

## 1. CU（Compute Unit）是什么？

### 定义
**CU（Compute Unit）** 是函数计算的计费单位，用于统一衡量计算资源消耗。

### CU的计算公式
```
CU = (内存大小 × 执行时长) + (GPU显存 × GPU执行时长)
```

**具体说明：**
- **内存CU** = 内存大小(GB) × 执行时长(秒) × 系数
- **GPU CU** = GPU显存(GB) × GPU执行时长(秒) × 系数
- 系数通常为1，但不同资源类型可能有不同系数

### 示例计算

**场景1: 纯CPU计算**
- 内存：8192 MB (8 GB)
- 执行时长：30秒
- CU消耗 = 8 GB × 30秒 = 240 CU

**场景2: GPU计算**
- 内存：8192 MB (8 GB)
- GPU显存：16384 MB (16 GB)
- 执行时长：60秒
- CU消耗 = (8 GB × 60秒) + (16 GB × 60秒) = 480 + 960 = 1440 CU

**场景3: 冷启动**
- 冷启动时间：10秒（不计入执行时长）
- 实际执行：30秒
- 只计算30秒的CU消耗

## 2. GPU计算资源调用

### GPU实例类型

阿里云函数计算提供以下GPU实例类型：

#### 2.1 GPU规格
- **GPU显存**: 16384 MB (16 GB) 起
- **GPU型号**: 通常为 NVIDIA T4 或 V100
- **CUDA版本**: 11.8（与PyTorch镜像匹配）

#### 2.2 如何启用GPU

**方法1: 控制台配置**
1. 创建函数时选择"GPU实例"
2. 设置GPU显存大小（如16384 MB）
3. 选择GPU型号

**方法2: 配置文件**
```yaml
functions:
  translate:
    gpuMemorySize: 16384  # 16GB GPU显存
    instanceType: g1  # GPU实例类型
```

**方法3: 代码检测**
```python
import torch

# 检测GPU是否可用
if torch.cuda.is_available():
    device = "cuda"
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3} GB")
else:
    device = "cpu"
    print("GPU not available, using CPU")
```

### GPU资源分配

**重要概念：**
- **活跃GPU使用量**: 函数执行期间使用的GPU资源
- **闲置GPU使用量**: 函数启动/停止时的GPU资源占用
- **GPU预热**: 可以使用预留实例减少冷启动

### GPU使用示例

```python
# 在函数中正确使用GPU
import torch
from manga_translator import MangaTranslator, Config

def handler(event, context):
    # 检查GPU可用性
    if torch.cuda.is_available():
        device = "cuda"
        # 设置GPU内存分配策略
        torch.cuda.set_per_process_memory_fraction(0.9)  # 使用90%显存
    else:
        device = "cpu"
    
    # 创建配置，指定使用GPU
    config = Config()
    config.device = device
    
    # 执行翻译（会自动使用GPU）
    translator = MangaTranslator(config)
    result = await translator.translate(image)
    
    return result
```

## 3. 价格计算详解

### 3.1 计费项

函数计算按以下项目计费：

#### 基础计费项
1. **函数调用次数** (Invocation)
   - 每次函数调用计费
   - 免费额度：每月100万次

2. **活跃vCPU使用量** (Active vCPU)
   - 函数执行期间的CPU使用
   - 按GB-秒计费

3. **活跃内存使用量** (Active Memory)
   - 函数执行期间的内存使用
   - 按GB-秒计费

4. **活跃GPU使用量** (Active GPU)
   - 函数执行期间的GPU使用
   - 按GB-秒计费（最贵）

5. **闲置vCPU使用量** (Idle vCPU)
   - 函数启动/停止时的CPU占用
   - 按GB-秒计费

6. **闲置GPU使用量** (Idle GPU)
   - 函数启动/停止时的GPU占用
   - 按GB-秒计费

7. **公网出流量** (Outbound Traffic)
   - 函数访问公网的流量
   - 按GB计费

8. **磁盘使用量** (Disk)
   - 临时磁盘使用
   - 按GB-小时计费

### 3.2 价格表（参考，以实际为准）

#### 华东1（杭州）价格示例

**CPU实例：**
- 调用次数：¥0.0133/万次
- 活跃vCPU：¥0.000110592/GB-秒
- 活跃内存：¥0.000009216/GB-秒
- 闲置vCPU：¥0.000009216/GB-秒

**GPU实例（T4）：**
- 调用次数：¥0.0133/万次
- 活跃GPU：¥0.00011/GB-秒（约是CPU的12倍）
- 闲置GPU：¥0.0000092/GB-秒
- 活跃vCPU：¥0.000110592/GB-秒
- 活跃内存：¥0.000009216/GB-秒

**公网流量：**
- 中国内地：¥0.8/GB
- 非中国内地：¥0.5/GB

### 3.3 实际成本计算示例

#### 示例1: CPU翻译任务

**配置：**
- 内存：8192 MB (8 GB)
- 执行时长：30秒
- 调用次数：1000次/天

**日成本计算：**
```
调用次数成本 = 1000次 × ¥0.0133/万次 = ¥0.00133
活跃内存成本 = 8 GB × 30秒 × 1000次 × ¥0.000009216/GB-秒 = ¥2.21
闲置vCPU成本 = 8 GB × 5秒(启动时间) × 1000次 × ¥0.000009216/GB-秒 = ¥0.37

日总成本 ≈ ¥2.58
月总成本 ≈ ¥77.4
```

#### 示例2: GPU翻译任务

**配置：**
- 内存：8192 MB (8 GB)
- GPU显存：16384 MB (16 GB)
- 执行时长：60秒（GPU加速后更快）
- 调用次数：1000次/天

**日成本计算：**
```
调用次数成本 = 1000次 × ¥0.0133/万次 = ¥0.00133
活跃GPU成本 = 16 GB × 60秒 × 1000次 × ¥0.00011/GB-秒 = ¥105.6
活跃内存成本 = 8 GB × 60秒 × 1000次 × ¥0.000009216/GB-秒 = ¥4.42
闲置GPU成本 = 16 GB × 10秒 × 1000次 × ¥0.0000092/GB-秒 = ¥1.47

日总成本 ≈ ¥111.5
月总成本 ≈ ¥3345
```

**注意：** GPU成本是CPU的约43倍！

### 3.4 试用额度说明

**每月15万CU免费额度：**

**CU换算：**
- 1 CU ≈ 1 GB-秒（简化计算）

**可用资源示例：**
```
15万CU = 150,000 GB-秒

场景1: CPU任务（8GB内存）
可用时长 = 150,000 / 8 = 18,750秒 = 312.5分钟 = 5.2小时
如果每次30秒，可调用 = 18,750 / 30 = 625次

场景2: GPU任务（16GB GPU + 8GB内存 = 24GB）
可用时长 = 150,000 / 24 = 6,250秒 = 104分钟 = 1.7小时
如果每次60秒，可调用 = 6,250 / 60 = 104次
```

**结论：** 试用额度更适合CPU任务，GPU任务消耗很快。

## 4. 成本优化策略

### 4.1 选择合适的资源配置

**CPU vs GPU：**
- **CPU**: 成本低，速度慢，适合简单任务
- **GPU**: 成本高，速度快，适合复杂任务

**建议：**
- 测试阶段：使用CPU（4096MB内存）
- 生产环境：根据实际需求选择
- 批量处理：考虑使用GPU提高效率

### 4.2 减少执行时长

1. **模型优化**
   - 使用更小的模型
   - 模型量化（INT8）
   - 模型剪枝

2. **代码优化**
   - 异步处理
   - 批量处理
   - 缓存结果

3. **配置优化**
   - 合理设置超时时间
   - 避免不必要的等待

### 4.3 减少冷启动

1. **预留实例**
   - 保持实例常驻
   - 减少启动时间
   - 需要额外费用

2. **实例复用**
   - 合理设置实例并发度
   - 复用已启动的实例

3. **预热策略**
   - 定期调用保持实例活跃
   - 使用定时触发器

### 4.4 减少闲置资源

1. **快速启动**
   - 优化镜像大小
   - 减少依赖加载时间

2. **快速停止**
   - 及时释放资源
   - 避免长时间占用

### 4.5 流量优化

1. **使用内网**
   - 函数与OSS/NAS使用内网
   - 避免公网流量费用

2. **CDN加速**
   - 结果图片使用CDN
   - 减少回源流量

## 5. 成本估算工具

### 5.1 简单估算公式

```python
def estimate_cost(
    memory_gb: float,      # 内存(GB)
    gpu_memory_gb: float,  # GPU显存(GB)，0表示不使用GPU
    execution_time: float, # 执行时长(秒)
    idle_time: float,      # 闲置时长(秒)
    daily_invocations: int # 每日调用次数
):
    """估算每日成本"""
    
    # 价格（华东1，参考值）
    PRICE_INVOCATION = 0.0133 / 10000  # 每次调用
    PRICE_ACTIVE_MEMORY = 0.000009216  # GB-秒
    PRICE_ACTIVE_GPU = 0.00011  # GB-秒
    PRICE_IDLE_GPU = 0.0000092  # GB-秒
    
    # 调用次数成本
    invocation_cost = daily_invocations * PRICE_INVOCATION
    
    # 活跃内存成本
    active_memory_cost = memory_gb * execution_time * daily_invocations * PRICE_ACTIVE_MEMORY
    
    # GPU成本
    gpu_cost = 0
    if gpu_memory_gb > 0:
        # 活跃GPU成本
        active_gpu_cost = gpu_memory_gb * execution_time * daily_invocations * PRICE_ACTIVE_GPU
        # 闲置GPU成本
        idle_gpu_cost = gpu_memory_gb * idle_time * daily_invocations * PRICE_IDLE_GPU
        gpu_cost = active_gpu_cost + idle_gpu_cost
    
    total_daily = invocation_cost + active_memory_cost + gpu_cost
    total_monthly = total_daily * 30
    
    return {
        "daily_cost": total_daily,
        "monthly_cost": total_monthly,
        "breakdown": {
            "invocation": invocation_cost,
            "memory": active_memory_cost,
            "gpu": gpu_cost
        }
    }

# 示例：CPU任务
cpu_cost = estimate_cost(
    memory_gb=8,
    gpu_memory_gb=0,
    execution_time=30,
    idle_time=5,
    daily_invocations=1000
)
print(f"CPU任务日成本: ¥{cpu_cost['daily_cost']:.2f}")
print(f"CPU任务月成本: ¥{cpu_cost['monthly_cost']:.2f}")

# 示例：GPU任务
gpu_cost = estimate_cost(
    memory_gb=8,
    gpu_memory_gb=16,
    execution_time=60,
    idle_time=10,
    daily_invocations=100
)
print(f"GPU任务日成本: ¥{gpu_cost['daily_cost']:.2f}")
print(f"GPU任务月成本: ¥{gpu_cost['monthly_cost']:.2f}")
```

## 6. 实际使用建议

### 6.1 开发测试阶段
- 使用CPU实例（4096MB内存）
- 充分利用15万CU免费额度
- 测试不同配置的成本

### 6.2 生产环境
- 根据实际需求选择CPU/GPU
- 监控实际使用量和成本
- 设置预算告警
- 定期优化资源配置

### 6.3 成本控制
- 设置月度预算
- 配置成本告警
- 定期审查使用情况
- 优化高成本操作

## 7. 监控和告警

### 7.1 查看使用量
1. 登录函数计算控制台
2. 查看"使用量统计"
3. 分析各计费项的使用情况

### 7.2 设置告警
1. 在云监控中设置预算告警
2. 设置CU使用量告警
3. 设置费用告警

## 总结

**关键要点：**
1. **CU是统一计费单位**，综合了内存、GPU、执行时长
2. **GPU成本远高于CPU**，需要权衡速度和成本
3. **试用额度有限**，GPU任务消耗很快
4. **优化执行时长**是降低成本的关键
5. **合理配置资源**可以显著降低成本

**建议：**
- 先用CPU测试，验证功能
- 根据实际需求选择GPU
- 持续监控和优化成本
- 充分利用免费额度


