"""检查训练数据的时间对齐和标签编码问题"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pandas as pd
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import asyncio
from dotenv import load_dotenv
from trade_alpha.config import load_config
from trade_alpha.dao import StockDaily, StockList, TrainingResult, ModelConfig
from trade_alpha.predict.training_service import _create_classification_labels
from trade_alpha.predict.config_service import get_config_by_id


async def init_db():
    """初始化数据库"""
    config = load_config()
    client = AsyncIOMotorClient(config.mongodb_uri)
    database = client[config.mongodb_db]
    
    await init_beanie(database=database, document_models=[
        StockDaily, StockList, TrainingResult, ModelConfig
    ])


async def check_training_alignment():
    """检查训练数据的时间对齐和标签编码问题"""
    await init_db()
    
    # 获取最新的训练
    latest_training = await TrainingResult.find_one(sort=[(TrainingResult.created_at, -1)])
    
    if not latest_training:
        print("没有找到训练记录")
        return
    
    print(f"检查训练: {latest_training.name} (ID: {latest_training.id})")
    print(f"股票数量: {len(latest_training.ts_codes)}")
    print(f"训练时间范围: {latest_training.start_date} ~ {latest_training.end_date}")
    print()
    
    # 获取训练用的配置
    config = await get_config_by_id(latest_training.config_id)
    if not config:
        print("找不到训练配置")
        return
    
    print(f"预测周期: {config.classification_horizons}")
    print(f"阈值: {config.classification_threshold}")
    print()
    
    # 加载第一只股票的数据做验证
    ts_code = latest_training.ts_codes[0]
    print(f"验证股票: {ts_code}")
    
    records = await StockDaily.find(
        StockDaily.ts_code == ts_code,
        StockDaily.trade_date >= latest_training.start_date,
        StockDaily.trade_date <= latest_training.end_date
    ).sort(StockDaily.trade_date).to_list()
    
    if not records:
        print(f"{ts_code} 没有数据")
        return
    
    df = pd.DataFrame([r.model_dump() for r in records])
    df["ts_code"] = ts_code
    
    print(f"原始数据行数: {len(df)}")
    print(f"日期范围: {df['trade_date'].iloc[0]} ~ {df['trade_date'].iloc[-1]}")
    print()
    
    # 生成标签
    horizons = config.classification_horizons
    threshold = config.classification_threshold
    labeled_df = _create_classification_labels(df, horizons, threshold)
    
    print(f"标签生成后行数: {len(labeled_df)}")
    print(f"丢弃行数: {len(df) - len(labeled_df)}")
    print()
    
    # 检查第一行
    print("=" * 80)
    print("检查第一行数据（特征与标签对齐）")
    print("=" * 80)
    first_row = labeled_df.iloc[0]
    print(f"交易日期: {first_row['trade_date']}")
    print(f"收盘价: {first_row['close']}")
    print()
    
    # 检查标签是未来数据
    for h in horizons:
        label_col = f"label_{h}d"
        label = first_row[label_col]
        
        # 找到未来的日期
        curr_date = first_row['trade_date']
        future_idx = labeled_df[labeled_df['trade_date'] > curr_date].index
        
        if len(future_idx) >= h:
            h_days_later_row = labeled_df.iloc[future_idx[h-1]]
            actual_return = (h_days_later_row['close'] - first_row['close']) / first_row['close']
            
            print(f"未来 {h} 天:")
            print(f"  日期: {h_days_later_row['trade_date']}")
            print(f"  收盘价: {h_days_later_row['close']}")
            print(f"  涨跌幅: {actual_return:.4%}")
            print(f"  标签值: {label} (1=涨, 0=平, -1=跌)")
            print(f"  预期标签: 1 ({actual_return:.2%} > {threshold})" if actual_return > threshold else
                  f"  预期标签: -1 ({actual_return:.2%} < -{threshold})" if actual_return < -threshold else
                  f"  预期标签: 0")
            print(f"  标签一致性: {'✓ 正确' if label == (1 if actual_return > threshold else (-1 if actual_return < -threshold else 0)) else '✗ 错误'}")
            print()
    
    # 检查标签编码
    print("=" * 80)
    print("检查标签编码")
    print("=" * 80)
    for h in horizons:
        label_col = f"label_{h}d"
        unique_labels = sorted(labeled_df[label_col].unique())
        print(f"{label_col} 唯一值: {unique_labels}")
        print(f"  是否包含 [-1, 0, 1]: {set(unique_labels) == {-1, 0, 1}}")
        print(f"  各标签数量:")
        for label in sorted(unique_labels):
            count = (labeled_df[label_col] == label).sum()
            print(f"    {label}: {count}")
        print()
    
    # 检查训练模型的标签映射（如果有模型文件）
    print("=" * 80)
    print("检查模型标签映射（需要加载模型文件）")
    print("=" * 80)
    
    if latest_training.model_path and os.path.exists(latest_training.model_path):
        print(f"模型文件: {latest_training.model_path}")
        try:
            import pickle
            data = pickle.load(open(latest_training.model_path, 'rb'))
            label_mapping = data.get('label_mapping', {})
            
            if label_mapping:
                print(f"模型中包含的标签映射:")
                for target, mapping in label_mapping.items():
                    print(f"  {target}: {mapping}")
                    print(f"    映射方向: index -> label")
                    print(f"    reverse: {dict((v, k) for k, v in mapping.items())}")
                print()
                
                print(f"predict_proba 的索引映射:")
                print(f"  proba[0] -> label = -1 (跌)")
                print(f"  proba[1] -> label = 0  (平)")
                print(f"  proba[2] -> label = 1  (涨)")
                print()
        except Exception as e:
            print(f"加载模型失败: {e}")
    else:
        print(f"模型文件不存在: {latest_training.model_path}")
        print()
    
    print("=" * 80)
    print("检查完毕")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(check_training_alignment())
