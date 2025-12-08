#!/usr/bin/env python3
"""
漫画翻译单次成本分析
基于实际翻译流程和函数计算价格
"""
from fc_cost_calculator import FCCostCalculator, FCPrice

def analyze_single_translation_cost():
    """分析单张漫画翻译的成本"""
    calculator = FCCostCalculator()
    
    print("=" * 70)
    print("单张漫画翻译成本分析")
    print("=" * 70)
    
    # 实际翻译流程耗时分析
    # 基于典型漫画图片（2000x3000像素，包含10-20个文本区域）
    
    scenarios = [
        {
            "name": "场景1: CPU + 离线翻译器（Sugoi/NLLB）",
            "memory_gb": 8,
            "gpu_memory_gb": 0,
            "execution_time_sec": 45,  # CPU较慢
            "idle_time_sec": 8,
            "translator_cost": 0,  # 离线翻译，无API费用
            "description": "使用CPU和离线翻译模型，成本最低但速度较慢"
        },
        {
            "name": "场景2: CPU + DeepSeek API",
            "memory_gb": 8,
            "gpu_memory_gb": 0,
            "execution_time_sec": 30,  # API翻译较快
            "idle_time_sec": 5,
            "translator_cost": 0.002,  # DeepSeek API费用（约$0.001/1K tokens，假设500 tokens）
            "description": "使用CPU和DeepSeek API，平衡成本和速度"
        },
        {
            "name": "场景3: GPU + 离线翻译器",
            "memory_gb": 8,
            "gpu_memory_gb": 16,
            "execution_time_sec": 20,  # GPU加速，速度快
            "idle_time_sec": 10,
            "translator_cost": 0,
            "description": "使用GPU加速，速度快但FC成本高"
        },
        {
            "name": "场景4: GPU + DeepSeek API",
            "memory_gb": 8,
            "gpu_memory_gb": 16,
            "execution_time_sec": 15,  # GPU + API，最快
            "idle_time_sec": 8,
            "translator_cost": 0.002,
            "description": "GPU加速 + API翻译，速度最快但成本最高"
        },
        {
            "name": "场景5: 优化配置（4GB内存 + CPU）",
            "memory_gb": 4,
            "gpu_memory_gb": 0,
            "execution_time_sec": 60,  # 内存小，可能更慢
            "idle_time_sec": 5,
            "translator_cost": 0.002,
            "description": "降低内存配置，成本最低但速度最慢"
        }
    ]
    
    results = []
    
    for scenario in scenarios:
        print(f"\n{scenario['name']}")
        print("-" * 70)
        print(f"说明: {scenario['description']}")
        print(f"配置: {scenario['memory_gb']}GB内存", end="")
        if scenario['gpu_memory_gb'] > 0:
            print(f", {scenario['gpu_memory_gb']}GB GPU", end="")
        print(f", {scenario['execution_time_sec']}秒执行时间")
        
        # 计算FC成本（单次调用）
        cost_result = calculator.calculate_daily_cost(
            memory_gb=scenario['memory_gb'],
            gpu_memory_gb=scenario['gpu_memory_gb'],
            execution_time_sec=scenario['execution_time_sec'],
            idle_time_sec=scenario['idle_time_sec'],
            daily_invocations=1  # 单次调用
        )
        
        # 单次成本
        single_fc_cost = cost_result['daily_cost']
        total_cost = single_fc_cost + scenario['translator_cost']
        
        # CU消耗
        cu_per_call = cost_result['cu_usage']['daily_cu']
        
        print(f"\n成本明细:")
        print(f"  FC计算成本: ¥{single_fc_cost:.4f}")
        if scenario['translator_cost'] > 0:
            print(f"  翻译API成本: ¥{scenario['translator_cost']:.4f}")
        print(f"  总成本: ¥{total_cost:.4f}")
        print(f"  CU消耗: {cu_per_call:.0f} CU")
        
        # 免费额度可用次数
        free_quota = calculator.estimate_free_quota_usage(
            scenario['memory_gb'],
            scenario['gpu_memory_gb'],
            scenario['execution_time_sec']
        )
        print(f"  15万CU免费额度可用: {free_quota['available_invocations']:.0f} 次")
        
        results.append({
            "scenario": scenario['name'],
            "fc_cost": single_fc_cost,
            "api_cost": scenario['translator_cost'],
            "total_cost": total_cost,
            "cu_usage": cu_per_call,
            "execution_time": scenario['execution_time_sec']
        })
    
    # 成本对比
    print("\n" + "=" * 70)
    print("成本对比总结")
    print("=" * 70)
    print(f"{'场景':<30} {'总成本':<12} {'CU消耗':<12} {'执行时间':<10}")
    print("-" * 70)
    
    for r in results:
        print(f"{r['scenario']:<30} ¥{r['total_cost']:.4f}    {r['cu_usage']:>8.0f} CU    {r['execution_time']:>6}秒")
    
    # 推荐方案
    print("\n" + "=" * 70)
    print("推荐方案")
    print("=" * 70)
    
    min_cost = min(r['total_cost'] for r in results)
    min_cost_scenario = next(r for r in results if r['total_cost'] == min_cost)
    
    fastest = min(r['execution_time'] for r in results)
    fastest_scenario = next(r for r in results if r['execution_time'] == fastest)
    
    best_value = min(results, key=lambda x: x['total_cost'] / x['execution_time'])
    
    print(f"💰 成本最低: {min_cost_scenario['scenario']}")
    print(f"   单次成本: ¥{min_cost_scenario['total_cost']:.4f}")
    print(f"   执行时间: {min_cost_scenario['execution_time']}秒")
    
    print(f"\n⚡ 速度最快: {fastest_scenario['scenario']}")
    print(f"   单次成本: ¥{fastest_scenario['total_cost']:.4f}")
    print(f"   执行时间: {fastest_scenario['execution_time']}秒")
    
    print(f"\n🎯 性价比最高: {best_value['scenario']}")
    print(f"   单次成本: ¥{best_value['total_cost']:.4f}")
    print(f"   执行时间: {best_value['execution_time']}秒")
    print(f"   成本/时间比: ¥{best_value['total_cost']/best_value['execution_time']:.6f}/秒")
    
    # 批量成本分析
    print("\n" + "=" * 70)
    print("批量翻译成本分析（100张漫画）")
    print("=" * 70)
    
    batch_scenarios = [
        ("CPU + 离线翻译", 8, 0, 45, 0),
        ("CPU + DeepSeek", 8, 0, 30, 0.002),
        ("GPU + DeepSeek", 8, 16, 15, 0.002),
    ]
    
    for name, mem, gpu, time, api_cost in batch_scenarios:
        batch_result = calculator.calculate_daily_cost(
            memory_gb=mem,
            gpu_memory_gb=gpu,
            execution_time_sec=time,
            idle_time_sec=8,
            daily_invocations=100
        )
        total_batch_cost = batch_result['daily_cost'] + (api_cost * 100)
        print(f"{name:<20}: ¥{total_batch_cost:.2f} (平均¥{total_batch_cost/100:.4f}/张)")


if __name__ == "__main__":
    analyze_single_translation_cost()


