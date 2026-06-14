import asyncio
import numpy as np
from collections import defaultdict
from trade_alpha.dao.mongodb import init_db
from trade_alpha.config import load_config
from trade_alpha.dao.execution import ExecutionResult
from trade_alpha.dao.execution_daily_snapshot import ExecutionDailySnapshot

async def main():
    config = load_config()
    await init_db()

    # Get latest 2025 full year run with all features
    results_list = await ExecutionResult.find(
        ExecutionResult.mode == 'backtest',
        ExecutionResult.status == 'completed',
        ExecutionResult.start_date == '20250101',
    ).sort('-created_at').to_list()

    result = None
    for r in results_list:
        ss = r.strategy_snapshot
        if not ss: continue
        name = getattr(ss, 'name', '')
        use_rup = getattr(ss, 'use_rank_up_priority', False)
        rup_cnt = getattr(ss, 'rank_up_count', 0)
        if use_rup and rup_cnt == 1 and 'live_long' in name:
            result = r
            break
    if not result:
        result = results_list[0] if results_list else None
    if not result:
        print("No results")
        return

    print(f"Analyzing: {getattr(result.strategy_snapshot, 'name', '?')}")

    snapshots = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == result.id
    ).sort('date').to_list()
    print(f"Snapshots: {len(snapshots)}")

    # Classify market regime by rolling 20-day baseline return
    regimes = {}
    for i, snap in enumerate(snapshots):
        if i < 20:
            continue
        first_val = snapshots[i-19].baseline_value
        last_val = snap.baseline_value
        if first_val > 0:
            ret = (last_val - first_val) / first_val
            if ret > 0.05:
                regimes[snap.date] = 'trending_up'
            elif ret < -0.03:
                regimes[snap.date] = 'trending_down'
            else:
                regimes[snap.date] = 'sideways'

    # Collect daily score statistics from predictions
    day_stats = []
    for snap in snapshots:
        date = snap.date
        regime = regimes.get(date, 'unknown')
        if regime == 'unknown' and snap.date >= snapshots[19].date:
            # Still classify using baseline value
            idx = next(i for i, s in enumerate(snapshots) if s.date == snap.date)
            if idx >= 20:
                first_val = snapshots[idx-19].baseline_value
                last_val = snap.baseline_value
                if first_val > 0:
                    ret = (last_val - first_val) / first_val
                    if ret > 0.05:
                        regime = 'trending_up'
                    elif ret < -0.03:
                        regime = 'trending_down'
                    else:
                        regime = 'sideways'
                    regimes[date] = regime
        elif regime == 'unknown':
            continue

        # Extract scores from predictions
        preds = snap.predictions or {}
        raw_scores = []
        composite_scores = []
        trend_bonus = []
        trend_penalty = []
        vol_penalty = []
        momentum_bonus = []
        momentum_penalty = []
        ranking_scores = []
        price_slopes = []
        price_r_squared = []
        price_avg_ranges = []
        rank_improvements = []

        for ts_code, p in preds.items():
            if not isinstance(p, dict):
                continue
            if p.get('score', 0) > 0:
                raw_scores.append(p.get('score', 0))
            composite_scores.append(p.get('composite_score', 0))
            ranking_scores.append(p.get('ranking_score', 0))
            if 'trend_bonus' in p:
                trend_bonus.append(p.get('trend_bonus', 0))
            if 'trend_penalty' in p:
                trend_penalty.append(p.get('trend_penalty', 0))
            if 'vol_penalty' in p:
                vol_penalty.append(p.get('vol_penalty', 0))
            if 'momentum_bonus' in p:
                momentum_bonus.append(p.get('momentum_bonus', 0))
            if 'momentum_penalty' in p:
                momentum_penalty.append(p.get('momentum_penalty', 0))
            if 'price_slope' in p:
                price_slopes.append(p.get('price_slope', 0))
            if 'price_r_squared' in p:
                price_r_squared.append(p.get('price_r_squared', 0))
            if 'price_avg_range' in p:
                price_avg_ranges.append(p.get('price_avg_range', 0))
            if 'rank_improvement' in p:
                rank_improvements.append(p.get('rank_improvement', 0))

        if not raw_scores:
            continue

        stats = {
            'date': date,
            'regime': regime,
            'raw_score_mean': np.mean(raw_scores),
            'raw_score_median': np.median(raw_scores),
            'raw_score_std': np.std(raw_scores),
            'raw_score_p25': np.percentile(raw_scores, 25),
            'raw_score_p75': np.percentile(raw_scores, 75),
            'raw_score_p90': np.percentile(raw_scores, 90),
            'raw_score_p10': np.percentile(raw_scores, 10),
            'raw_score_count': len(raw_scores),
            'composite_mean': np.mean(composite_scores),
            'composite_median': np.median(composite_scores),
            'composite_std': np.std(composite_scores),
            'ranking_mean': np.mean(ranking_scores),
            'ranking_std': np.std(ranking_scores),
            'trend_bonus_mean': np.mean(trend_bonus) if trend_bonus else 0,
            'trend_penalty_mean': np.mean(trend_penalty) if trend_penalty else 0,
            'vol_penalty_mean': np.mean(vol_penalty) if vol_penalty else 0,
            'momentum_bonus_mean': np.mean(momentum_bonus) if momentum_bonus else 0,
            'momentum_penalty_mean': np.mean(momentum_penalty) if momentum_penalty else 0,
            'price_slope_mean': np.mean(price_slopes) if price_slopes else 0,
            'price_slope_abs_mean': np.mean([abs(s) for s in price_slopes]) if price_slopes else 0,
            'price_r_squared_mean': np.mean(price_r_squared) if price_r_squared else 0,
            'price_avg_range_mean': np.mean(price_avg_ranges) if price_avg_ranges else 0,
            'rank_improvement_mean': np.mean(rank_improvements) if rank_improvements else 0,
            'rank_improvement_abs_mean': np.mean([abs(r) for r in rank_improvements]) if rank_improvements else 0,
            'rank_improvement_p90': np.percentile(rank_improvements, 90) if rank_improvements else 0,
            'buy_pct': sum(1 for p in preds.values() if isinstance(p, dict) and p.get('score', 0) > 0.30) / max(len(preds), 1) * 100,
            'excluded_count': sum(1 for p in preds.values() if isinstance(p, dict) and p.get('is_excluded', False)),
            'excluded_pct': sum(1 for p in preds.values() if isinstance(p, dict) and p.get('is_excluded', False)) / max(len(preds), 1) * 100,
            'total_count': len(preds),
        }
        day_stats.append(stats)

    # Group by regime
    regime_stats = defaultdict(list)
    for s in day_stats:
        regime_stats[s['regime']].append(s)

    print(f"\n{'='*100}")
    print(f"DAILY SCORE DISTRIBUTION BY MARKET REGIME")
    print(f"{'='*100}")

    metrics = [
        ('raw_score_mean', 'Raw Score Mean'),
        ('raw_score_median', 'Raw Score Median'),
        ('raw_score_std', 'Raw Score Std'),
        ('raw_score_p10', 'P10 Score'),
        ('raw_score_p25', 'P25 Score'),
        ('raw_score_p75', 'P75 Score'),
        ('raw_score_p90', 'P90 Score'),
        ('raw_score_count', '# Stocks > 0'),
        ('composite_mean', 'Composite Mean'),
        ('composite_std', 'Composite Std'),
        ('composite_median', 'Composite Median'),
        ('ranking_mean', 'Ranking Mean'),
        ('ranking_std', 'Ranking Std'),
        ('trend_bonus_mean', 'Trend Bonus Mean'),
        ('trend_penalty_mean', 'Trend Penalty Mean'),
        ('vol_penalty_mean', 'Vol Penalty Mean'),
        ('momentum_bonus_mean', 'Momentum Bonus Mean'),
        ('momentum_penalty_mean', 'Momentum Penalty Mean'),
        ('price_slope_mean', 'Price Slope Mean'),
        ('price_slope_abs_mean', '|Price Slope| Mean'),
        ('price_r_squared_mean', 'R² Mean'),
        ('price_avg_range_mean', 'Avg Range Mean'),
        ('rank_improvement_mean', 'Rank Impr. Mean'),
        ('rank_improvement_abs_mean', '|Rank Impr.| Mean'),
        ('rank_improvement_p90', 'Rank Impr. P90'),
        ('buy_pct', '% Stocks Score>0.30'),
        ('excluded_pct', '% Excluded Stocks'),
    ]

    for metric_key, metric_name in metrics:
        print(f"\n  {metric_name:25s} ", end="")
        for regime in ['trending_up', 'sideways', 'trending_down']:
            vals = [s[metric_key] for s in regime_stats[regime]]
            if vals:
                mean_v = np.mean(vals)
                std_v = np.std(vals)
                lo, hi = np.percentile(vals, 10), np.percentile(vals, 90)
                print(f" | {regime[:12]:12s} mean={mean_v:+.4f} sd={std_v:.4f} [p10={lo:+.4f} p90={hi:+.4f}]", end="")
        print()

    # Now test: can any metric SINGLE-HANDEDLY classify sideways vs trending?
    print(f"\n{'='*100}")
    print(f"DISCRIMINATION POWER: Can each metric separate sideways from trending?")
    print(f"(Measured by effect size = |mean_diff| / pooled_std)")
    print(f"{'='*100}")

    sideways_vals = regime_stats['sideways']
    up_vals = regime_stats['trending_up']

    if sideways_vals and up_vals:
        results = []
        for metric_key, metric_name in metrics:
            sv = np.array([s[metric_key] for s in sideways_vals])
            uv = np.array([s[metric_key] for s in up_vals])
            if len(sv) > 0 and len(uv) > 0:
                mean_diff = abs(np.mean(sv) - np.mean(uv))
                pooled_std = np.sqrt((np.std(sv)**2 + np.std(uv)**2) / 2)
                effect_size = mean_diff / pooled_std if pooled_std > 0 else 0
                results.append((effect_size, metric_name, metric_key, np.mean(sv), np.mean(uv)))

        results.sort(reverse=True)
        print(f"  {'Rank':<5s} {'Metric':30s} {'Effect Size':12s} {'Sideways Mean':15s} {'Trending Mean':15s}")
        print(f"  {'-'*5} {'-'*30} {'-'*12} {'-'*15} {'-'*15}")
        for rank, (es, mn, mk, sv_mean, uv_mean) in enumerate(results[:20], 1):
            print(f"  {rank:<5d} {mn:30s} {es:>10.2f}   {sv_mean:>+10.4f}      {uv_mean:>+10.4f}")

    # Now look at the TIME SERIES: do these metrics change slowly enough
    # to be a USEFUL market state indicator (not jumpy day to day)?
    # Test the top 3 metrics
    print(f"\n{'='*100}")
    print(f"STABILITY CHECK: Day-to-day correlation for top indicators")
    print(f"(High autocorrelation = smooth signal, good for threshold-based switching)")
    print(f"{'='*100}")

    for metric_key, metric_name in metrics[:3]:
        vals = [s[metric_key] for s in day_stats[20:]]  # skip warmup
        if len(vals) < 10:
            continue
        # Autocorrelation (lag 1)
        shifts = vals[1:]
        orig = vals[:-1]
        if np.std(orig) > 0 and np.std(shifts) > 0:
            corr = np.corrcoef(orig, shifts)[0, 1]
            print(f"  {metric_name:30s} lag-1 autocorrelation: {corr:.3f}")

asyncio.run(main())
