"""分析训练特征的质量、标准化流程和特征重要性"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pandas as pd
import numpy as np
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
from trade_alpha.config import load_config
from trade_alpha.dao import StockDaily, StockList, TrainingResult, ModelConfig
from trade_alpha.predict.training_service import _create_classification_labels
from trade_alpha.predict.config_service import get_config_by_id
from trade_alpha.predict.normalizers.cross_sectional import CrossSectionalNormalizer


async def init_db():
    config = load_config()
    client = AsyncIOMotorClient(config.mongodb_uri)
    database = client[config.mongodb_db]
    await init_beanie(database=database, document_models=[
        StockDaily, StockList, TrainingResult, ModelConfig
    ])


async def analyze_features():
    await init_db()
    
    # 获取最新训练
    latest_training = await TrainingResult.find_one(sort=[(TrainingResult.created_at, -1)])
    if not latest_training:
        print("没有找到训练记录")
        return
    
    print(f"分析训练: {latest_training.name}")
    print(f"训练ID: {latest_training.id}")
    print()
    
    # 获取配置
    config = await get_config_by_id(latest_training.config_id)
    if not config:
        print("找不到训练配置")
        return
    
    feature_fields = config.feature_fields
    horizons = config.classification_horizons
    threshold = config.classification_threshold
    
    print(f"特征数量: {len(feature_fields)}")
    print(f"特征列表: {feature_fields}")
    print(f"预测周期: {horizons}")
    print(f"阈值: {threshold}")
    print()
    
    # 加载训练数据
    ts_codes = latest_training.ts_codes[:5]  # 取前5只股票分析
    print(f"分析股票数量: {len(ts_codes)}")
    
    all_dfs = []
    for ts_code in ts_codes:
        records = await StockDaily.find(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date >= latest_training.start_date,
            StockDaily.trade_date <= latest_training.end_date
        ).sort(StockDaily.trade_date).to_list()
        
        if records:
            df = pd.DataFrame([r.model_dump() for r in records])
            df["ts_code"] = ts_code
            all_dfs.append(df)
    
    if not all_dfs:
        print("没有找到数据")
        return
    
    df = pd.concat(all_dfs, ignore_index=True)
    df = df.sort_values(["trade_date", "ts_code"])
    
    print(f"原始数据行数: {len(df)}")
    print(f"日期范围: {df['trade_date'].min()} ~ {df['trade_date'].max()}")
    print()
    
    # ========== 1. 特征质量分析 ==========
    print("=" * 80)
    print("1. 原始特征质量分析")
    print("=" * 80)
    
    # 检查缺失值
    missing_stats = df[feature_fields].isnull().sum()
    missing_pct = (missing_stats / len(df) * 100).round(2)
    
    print("缺失值统计:")
    missing_df = pd.DataFrame({
        "缺失数量": missing_stats,
        "缺失比例(%)": missing_pct
    }).sort_values("缺失比例(%)", ascending=False)
    print(missing_df.to_string())
    print()
    
    # 检查特征统计量
    print("特征统计量（前10个特征）:")
    stats = df[feature_fields[:10]].describe().round(4)
    print(stats.to_string())
    print()
    
    # 检查异常值（Z-score > 3 的比例）
    print("异常值比例（Z-score > 3）:")
    outlier_pct = {}
    for field in feature_fields[:10]:
        mean = df[field].mean()
        std = df[field].std()
        if std > 0:
            z_scores = np.abs((df[field] - mean) / std)
            outlier_pct[field] = (z_scores > 3).mean() * 100
        else:
            outlier_pct[field] = 0
    
    outlier_df = pd.DataFrame({"异常值比例(%)": outlier_pct}).sort_values("异常值比例(%)", ascending=False)
    print(outlier_df.to_string())
    print()
    
    # ========== 2. 标准化流程分析 ==========
    print("=" * 80)
    print("2. 标准化流程分析")
    print("=" * 80)
    
    # 生成标签
    df_with_labels = _create_classification_labels(df, horizons, threshold)
    print(f"生成标签后行数: {len(df_with_labels)}")
    print(f"丢弃行数: {len(df) - len(df_with_labels)}")
    print()
    
    # 创建标准化器
    normalizer = CrossSectionalNormalizer(
        standardize_fields=config.standardize_fields,
        winsorize_fields=config.winsorize_fields or [],
        output_fields=config.output_fields
    )
    
    # 执行标准化
    normalized_df = normalizer.normalize(df_with_labels)
    print(f"标准化后行数: {len(normalized_df)}")
    print()
    
    # 检查标准化后的特征分布
    print("标准化后特征统计量（前10个特征）:")
    normalized_stats = normalized_df[feature_fields[:10]].describe().round(4)
    print(normalized_stats.to_string())
    print()
    
    # 检查横截面标准化效果（取某一天为例）
    sample_date = df_with_labels['trade_date'].iloc[50]
    print(f"横截面标准化效果示例（日期: {sample_date}）:")
    day_df = normalized_df[df_with_labels['trade_date'] == sample_date]
    print(f"当日股票数量: {len(day_df)}")
    print(f"各特征均值（应该接近0）:")
    day_means = day_df[feature_fields[:5]].mean().round(4)
    print(day_means.to_string())
    print(f"各特征标准差（应该接近1）:")
    day_stds = day_df[feature_fields[:5]].std().round(4)
    print(day_stds.to_string())
    print()
    
    # ========== 3. 特征重要性分析 ==========
    print("=" * 80)
    print("3. 特征重要性分析")
    print("=" * 80)
    
    model_path = latest_training.model_path
    if model_path and os.path.exists(model_path):
        try:
            import pickle
            model_data = pickle.load(open(model_path, 'rb'))
            models = model_data.get('models', {})
            
            for target, model in models.items():
                print(f"\n{target} 的特征重要性:")
                
                if hasattr(model, 'feature_importances_'):
                    importances = model.feature_importances_
                    feature_importance_df = pd.DataFrame({
                        "特征": feature_fields,
                        "重要性": importances
                    }).sort_values("重要性", ascending=False)
                    print(feature_importance_df.to_string())
                    
                    # 累计重要性
                    cum_importance = feature_importance_df['重要性'].cumsum()
                    print("\n累计重要性:")
                    for i in [5, 10, 15, 20]:
                        if i <= len(feature_importance_df):
                            print(f"  前{i}个特征累计: {cum_importance.iloc[i-1]:.4f}")
                else:
                    print("  模型没有 feature_importances_ 属性")
        except Exception as e:
            print(f"加载模型失败: {e}")
    else:
        print(f"模型文件不存在: {model_path}")
        print()
    
    # ========== 4. 标签与特征相关性分析 ==========
    print("=" * 80)
    print("4. 标签与特征相关性分析")
    print("=" * 80)
    
    # 合并标准化数据和标签
    combined_df = df_with_labels.copy()
    combined_df[feature_fields] = normalized_df[feature_fields]
    
    for h in horizons:
        label_col = f"label_{h}d"
        print(f"\n{label_col} 与特征的相关性（绝对值降序）:")
        
        correlations = []
        for field in feature_fields:
            corr = combined_df[[field, label_col]].dropna().corr().iloc[0, 1]
            correlations.append({"特征": field, "相关系数": abs(corr)})
        
        corr_df = pd.DataFrame(correlations).sort_values("相关系数", ascending=False)
        print(corr_df.head(10).to_string())
        print(f"最高相关系数: {corr_df['相关系数'].max():.4f}")
        print(f"平均相关系数: {corr_df['相关系数'].mean():.4f}")
    
    # ========== 5. 总结 ==========
    print("\n" + "=" * 80)
    print("5. 分析总结")
    print("=" * 80)
    
    # 特征质量评估
    high_missing = missing_pct[missing_pct > 10].count()
    print(f"- 缺失值比例 >10% 的特征数: {high_missing}")
    
    # 标准化效果评估
    mean_std_ok = (normalized_stats.loc['mean'].abs() < 0.1).all()
    print(f"- 标准化后均值接近0: {'✓' if mean_std_ok else '✗'}")
    
    # 相关性评估
    avg_corr = corr_df['相关系数'].mean()
    print(f"- 特征与标签平均相关系数: {avg_corr:.4f}")
    print(f"- 最高特征相关系数: {corr_df['相关系数'].max():.4f}")
    
    if avg_corr < 0.05:
        print("\n⚠️ 警告: 特征与标签相关性极低，可能缺乏预测能力")
    elif avg_corr < 0.1:
        print("\n⚠️ 注意: 特征与标签相关性较低")
    else:
        print("\n✓ 特征与标签有一定相关性")


if __name__ == "__main__":
    asyncio.run(analyze_features())
