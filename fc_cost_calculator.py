#!/usr/bin/env python3
"""
阿里云函数计算成本估算工具
"""
from typing import Dict
from dataclasses import dataclass

@dataclass
class FCPrice:
    """函数计算价格配置（华东1-杭州，参考价格）"""
    # 调用次数
    invocation_per_10k: float = 0.0133  # 每万次
    
    # CPU实例
    active_vcpu_per_gb_sec: float = 0.000110592
    active_memory_per_gb_sec: float = 0.000009216
    idle_vcpu_per_gb_sec: float = 0.000009216
    
    # GPU实例（T4）
    active_gpu_per_gb_sec: float = 0.00011
    idle_gpu_per_gb_sec: float = 0.0000092
    
    # 公网流量
    traffic_cn_per_gb: float = 0.8
    traffic_overseas_per_gb: float = 0.5


class FCCostCalculator:
    """函数计算成本计算器"""
    
    def __init__(self, price: FCPrice = None):
        self.price = price or FCPrice()
    
    def calculate_daily_cost(
        self,
        memory_gb: float,
        gpu_memory_gb: float = 0,
        execution_time_sec: float = 30,
        idle_time_sec: float = 5,
        daily_invocations: int = 1000,
        traffic_gb: float = 0,
        traffic_overseas: bool = False
    ) -> Dict:
        """
        计算每日成本
        
        Args:
            memory_gb: 内存大小(GB)
            gpu_memory_gb: GPU显存大小(GB)，0表示不使用GPU
            execution_time_sec: 平均执行时长(秒)
            idle_time_sec: 平均闲置时长(秒)
            daily_invocations: 每日调用次数
            traffic_gb: 每日公网流量(GB)
            traffic_overseas: 是否为海外流量
        """
        # 调用次数成本
        invocation_cost = daily_invocations * (self.price.invocation_per_10k / 10000)
        
        # 活跃内存成本
        active_memory_cost = (
            memory_gb * 
            execution_time_sec * 
            daily_invocations * 
            self.price.active_memory_per_gb_sec
        )
        
        # 活跃vCPU成本（通常与内存成比例，这里简化计算）
        active_vcpu_cost = (
            memory_gb * 
            execution_time_sec * 
            daily_invocations * 
            self.price.active_vcpu_per_gb_sec
        )
        
        # GPU成本
        gpu_cost = 0
        idle_gpu_cost = 0
        if gpu_memory_gb > 0:
            # 活跃GPU成本
            gpu_cost = (
                gpu_memory_gb * 
                execution_time_sec * 
                daily_invocations * 
                self.price.active_gpu_per_gb_sec
            )
            # 闲置GPU成本
            idle_gpu_cost = (
                gpu_memory_gb * 
                idle_time_sec * 
                daily_invocations * 
                self.price.idle_gpu_per_gb_sec
            )
        
        # 闲置vCPU成本
        idle_vcpu_cost = (
            memory_gb * 
            idle_time_sec * 
            daily_invocations * 
            self.price.idle_vcpu_per_gb_sec
        )
        
        # 流量成本
        traffic_cost = 0
        if traffic_gb > 0:
            if traffic_overseas:
                traffic_cost = traffic_gb * self.price.traffic_overseas_per_gb
            else:
                traffic_cost = traffic_gb * self.price.traffic_cn_per_gb
        
        # 总成本
        total_daily = (
            invocation_cost + 
            active_memory_cost + 
            active_vcpu_cost + 
            gpu_cost + 
            idle_gpu_cost + 
            idle_vcpu_cost + 
            traffic_cost
        )
        
        return {
            "daily_cost": total_daily,
            "monthly_cost": total_daily * 30,
            "breakdown": {
                "invocation": invocation_cost,
                "active_memory": active_memory_cost,
                "active_vcpu": active_vcpu_cost,
                "gpu_active": gpu_cost,
                "gpu_idle": idle_gpu_cost,
                "idle_vcpu": idle_vcpu_cost,
                "traffic": traffic_cost
            },
            "cu_usage": {
                "daily_cu": (
                    memory_gb * execution_time_sec * daily_invocations +
                    gpu_memory_gb * execution_time_sec * daily_invocations
                ),
                "monthly_cu": (
                    memory_gb * execution_time_sec * daily_invocations * 30 +
                    gpu_memory_gb * execution_time_sec * daily_invocations * 30
                )
            }
        }
    
    def estimate_free_quota_usage(
        self,
        memory_gb: float,
        gpu_memory_gb: float = 0,
        execution_time_sec: float = 30,
        free_cu: float = 150000  # 15万CU免费额度
    ) -> Dict:
        """
        估算免费额度可用次数
        
        Args:
            memory_gb: 内存大小(GB)
            gpu_memory_gb: GPU显存大小(GB)
            execution_time_sec: 执行时长(秒)
            free_cu: 免费CU额度
        """
        # 每次调用消耗的CU
        cu_per_invocation = (
            memory_gb * execution_time_sec +
            gpu_memory_gb * execution_time_sec
        )
        
        # 可用次数
        available_invocations = free_cu / cu_per_invocation if cu_per_invocation > 0 else 0
        
        # 假设每天1000次调用
        daily_invocations = 1000
        available_days = available_invocations / daily_invocations if daily_invocations > 0 else 0
        
        return {
            "cu_per_invocation": cu_per_invocation,
            "available_invocations": available_invocations,
            "available_days": available_days,
            "free_quota_cu": free_cu
        }


def main():
    """示例使用"""
    calculator = FCCostCalculator()
    
    print("=" * 60)
    print("阿里云函数计算成本估算")
    print("=" * 60)
    
    # 场景1: CPU任务
    print("\n【场景1】CPU翻译任务")
    print("-" * 60)
    print("配置: 8GB内存, 30秒执行, 1000次/天")
    cpu_result = calculator.calculate_daily_cost(
        memory_gb=8,
        gpu_memory_gb=0,
        execution_time_sec=30,
        idle_time_sec=5,
        daily_invocations=1000
    )
    print(f"日成本: ¥{cpu_result['daily_cost']:.2f}")
    print(f"月成本: ¥{cpu_result['monthly_cost']:.2f}")
    print(f"日CU消耗: {cpu_result['cu_usage']['daily_cu']:.0f} CU")
    print(f"月CU消耗: {cpu_result['cu_usage']['monthly_cu']:.0f} CU")
    
    # 场景2: GPU任务
    print("\n【场景2】GPU翻译任务")
    print("-" * 60)
    print("配置: 8GB内存, 16GB GPU, 60秒执行, 100次/天")
    gpu_result = calculator.calculate_daily_cost(
        memory_gb=8,
        gpu_memory_gb=16,
        execution_time_sec=60,
        idle_time_sec=10,
        daily_invocations=100
    )
    print(f"日成本: ¥{gpu_result['daily_cost']:.2f}")
    print(f"月成本: ¥{gpu_result['monthly_cost']:.2f}")
    print(f"日CU消耗: {gpu_result['cu_usage']['daily_cu']:.0f} CU")
    print(f"月CU消耗: {gpu_result['cu_usage']['monthly_cu']:.0f} CU")
    
    # 免费额度分析
    print("\n【免费额度分析】")
    print("-" * 60)
    print("CPU任务（8GB, 30秒）:")
    cpu_quota = calculator.estimate_free_quota_usage(8, 0, 30)
    print(f"  每次消耗: {cpu_quota['cu_per_invocation']:.0f} CU")
    print(f"  可用次数: {cpu_quota['available_invocations']:.0f} 次")
    print(f"  按1000次/天可用: {cpu_quota['available_invocations']/1000:.1f} 天")
    
    print("\nGPU任务（16GB GPU + 8GB内存, 60秒）:")
    gpu_quota = calculator.estimate_free_quota_usage(24, 0, 60)  # 简化计算
    print(f"  每次消耗: {gpu_quota['cu_per_invocation']:.0f} CU")
    print(f"  可用次数: {gpu_quota['available_invocations']:.0f} 次")
    print(f"  按100次/天可用: {gpu_quota['available_invocations']/100:.1f} 天")
    
    # 成本对比
    print("\n【成本对比】")
    print("-" * 60)
    print(f"GPU成本是CPU的 {gpu_result['daily_cost']/cpu_result['daily_cost']:.1f} 倍")
    print(f"但GPU执行时间更长，实际效率需要根据任务复杂度评估")


if __name__ == "__main__":
    main()

