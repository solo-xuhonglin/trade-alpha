"""检查预测概率分布，判断模型是否有预测能力"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pandas as pd
import numpy as np
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
from trade_alpha.config import load_config
from trade_alpha.dao import StockDaily, ExecutionDailySnapshot, ExecutionResult


async def init_db():
    config = load_config()
    client = AsyncIOMotorClient(config.mongodb_uri)
    database = client[config.mongodb_db]
    await init_beanie(database=database, document_models=[
        ExecutionDailySnapshot, ExecutionResult
    ])


async def check_prediction_distribution():
    await init_db()
    
    # 获取最新回测
    latest_backtest = await ExecutionResult.find_one(sort=[(ExecutionResult.created_at, -1)])
    if not latest_backtest:
        print("没有找到回测记录")
        return
    
    print(f"检查回测: {latest_backtest.name}")
    print(f"股票: {latest_backtest.ts_code}")
    print(f"时间范围: {latest_backtest.start_date} ~ {latest_backtest.end_date}")
    print()
    
    # 获取所有快照
    snapshots = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == latest_backtest.id
    ).sort(ExecutionDailySnapshot.date).to_list()
    
    if not snapshots:
        print("没有找到快照数据")
        return
    
    print(f"快照数量: {len(snapshots)}")
    print()
    
    # 提取预测数据
    predictions = []
    for snap in snapshots:
        pred = snap.predictions.get(latest_backtest.ts_code)
        if pred:
            predictions.append({
                "date": snap.date,
                "score": pred.get("score"),
                "up_prob_3d": pred.get("up_prob_3d"),
                "down_prob_3d": pred.get("down_prob_3d"),
                "up_prob_5d": pred.get("up_prob_5d"),
                "down_prob_5d": pred.get("down_prob_5d"),
            })
    
    df = pd.DataFrame(predictions)
    print(f"有效预测天数: {len(df)}")
    print()
    
    # 统计分析
    print("=" * 80)
    print("预测得分 (score) 分布")
    print("=" * 80)
    print(f"得分范围: [{df['score'].min():.4f}, {df['score'].max():.4f}]")
    print(f"平均值: {df['score'].mean():.4f}")
    print(f"标准差: {df['score'].std():.4f}")
    print()
    
    # 得分分布区间
    print("得分区间分布:")
    print(f"  strongly bearish (score < -0.3): {len(df[df['score'] < -0.3])}")
    print(f"  bearish (-0.3 <= score < -0.1): {len(df[(df['score'] >= -0.3) & (df['score'] < -0.1)])}")
    print(f"  neutral (-0.1 <= score <= 0.1): {len(df[(df['score'] >= -0.1) & (df['score'] <= 0.1)])}")
    print(f"  bullish (0.1 < score <= 0.3): {len(df[(df['score'] > 0.1) & (df['score'] <= 0.3)])}")
    print(f"  strongly bullish (score > 0.3): {len(df[df['score'] > 0.3])}")
    print()
    
    # 3天概率差分析
    print("=" * 80)
    print("3日概率差 (up_prob_3d - down_prob_3d) 分布")
    print("=" * 80)
    prob_diff_3d = df['up_prob_3d'] - df['down_prob_3d']
    print(f"概率差范围: [{prob_diff_3d.min():.4f}, {prob_diff_3d.max():.4f}]")
    print(f"平均值: {prob_diff_3d.mean():.4f}")
    print(f"标准差: {prob_diff_3d.std():.4f}")
    print()
    
    # 5天概率差分析
    print("=" * 80)
    print("5日概率差 (up_prob_5d - down_prob_5d) 分布")
    print("=" * 80)
    prob_diff_5d = df['up_prob_5d'] - df['down_prob_5d']
    print(f"概率差范围: [{prob_diff_5d.min():.4f}, {prob_diff_5d.max():.4f}]")
    print(f"平均值: {prob_diff_5d.mean():.4f}")
    print(f"标准差: {prob_diff_5d.std():.4f}")
    print()
    
    # 概率集中度分析
    print("=" * 80)
    print("概率集中度分析（越接近1表示越确定，越接近0表示越模糊）")
    print("=" * 80)
    
    # 3日确定度 = |up_prob - down_prob|
    certainty_3d = np.abs(df['up_prob_3d'] - df['down_prob_3d'])
    print(f"3日确定度:")
    print(f"  平均值: {certainty_3d.mean():.4f}")
    print(f"  标准差: {certainty_3d.std():.4f}")
    print(f"  不确定天数 (|up-down| < 0.1): {len(df[certainty_3d < 0.1])}")
    print(f"  较确定天数 (|up-down| >= 0.2): {len(df[certainty_3d >= 0.2])}")
    print()
    
    # 5日确定度
    certainty_5d = np.abs(df['up_prob_5d'] - df['down_prob_5d'])
    print(f"5日确定度:")
    print(f"  平均值: {certainty_5d.mean():.4f}")
    print(f"  标准差: {certainty_5d.std():.4f}")
    print(f"  不确定天数 (|up-down| < 0.1): {len(df[certainty_5d < 0.1])}")
    print(f"  较确定天数 (|up-down| >= 0.2): {len(df[certainty_5d >= 0.2])}")
    print()
    
    # 看多看跌比例
    print("=" * 80)
    print("看多看跌预测比例")
    print("=" * 80)
    bullish_3d = len(df[df['up_prob_3d'] > df['down_prob_3d']])
    bearish_3d = len(df[df['up_prob_3d'] < df['down_prob_3d']])
    neutral_3d = len(df[df['up_prob_3d'] == df['down_prob_3d']])
    
    print(f"3日预测:")
    print(f"  看涨: {bullish_3d} ({bullish_3d/len(df)*100:.1f}%)")
    print(f"  看跌: {bearish_3d} ({bearish_3d/len(df)*100:.1f}%)")
    print(f"  持平: {neutral_3d} ({neutral_3d/len(df)*100:.1f}%)")
    print()
    
    bullish_5d = len(df[df['up_prob_5d'] > df['down_prob_5d']])
    bearish_5d = len(df[df['up_prob_5d'] < df['down_prob_5d']])
    neutral_5d = len(df[df['up_prob_5d'] == df['down_prob_5d']])
    
    print(f"5日预测:")
    print(f"  看涨: {bullish_5d} ({bullish_5d/len(df)*100:.1f}%)")
    print(f"  看跌: {bearish_5d} ({bearish_5d/len(df)*100:.1f}%)")
    print(f"  持平: {neutral_5d} ({neutral_5d/len(df)*100:.1f}%)")
    print()
    
    # 输出前10天数据验证
    print("=" * 80)
    print("前10天预测示例")
    print("=" * 80)
    print(df.head(10).to_string())
    
    print("\n" + "=" * 80)
    print("检查结论")
    print("=" * 80)
    
    if certainty_3d.mean() < 0.15:
        print("⚠️ 警告: 3日预测整体不确定度较高，概率差较小")
    else:
        print("✓ 3日预测有一定的确定度")
    
    if certainty_5d.mean() < 0.15:
        print("⚠️ 警告: 5日预测整体不确定度较高，概率差较小")
    else:
        print("✓ 5日预测有一定的确定度")


if __name__ == "__main__":
    asyncio.run(check_prediction_distribution())
