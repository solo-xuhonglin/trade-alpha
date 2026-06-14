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

    snapshots = await ExecutionDailySnapshot.find(
        ExecutionDailySnapshot.backtest_id == result.id
    ).sort('date').to_list()
    print(f"Snapshots: {len(snapshots)}")

    # Compute daily stats
    day_data = []
    for i, snap in enumerate(snapshots):
        date = snap.date
        preds = snap.predictions or {}

        raw_scores = []
        composite_scores = []
        trend_bonus_vals = []
        trend_penalty_vals = []
        momentum_bonus_vals = []
        momentum_penalty_vals = []
        price_slopes = []
        price_r_sq = []
        rank_imp = []

        for ts_code, p in preds.items():
            if not isinstance(p, dict):
                continue
            s = p.get('score', 0)
            if s > 0:
                raw_scores.append(s)
            composite_scores.append(p.get('composite_score', 0))
            trend_bonus_vals.append(p.get('trend_bonus', 0))
            trend_penalty_vals.append(p.get('trend_penalty', 0))
            momentum_bonus_vals.append(p.get('momentum_bonus', 0))
            momentum_penalty_vals.append(p.get('momentum_penalty', 0))
            price_slopes.append(p.get('price_slope', 0))
            price_r_sq.append(p.get('price_r_squared', 0))
            rank_imp.append(p.get('rank_improvement', 0))

        if not raw_scores:
            continue

        # Baseline return for classification
        base_ret = 0
        if i >= 20:
            bv0 = snapshots[i-19].baseline_value
            bv1 = snap.baseline_value
            if bv0 > 0:
                base_ret = (bv1 - bv0) / bv0

        day_data.append({
            'date': date,
            'base_20d_ret': base_ret,
            'regime': 'trending_up' if base_ret > 0.05 else ('trending_down' if base_ret < -0.03 else 'sideways'),
            'n_stocks_above_zero': len(raw_scores),
            'raw_score_mean': np.mean(raw_scores),
            'raw_score_median': np.median(raw_scores),
            'raw_score_std': np.std(raw_scores),
            'raw_score_p10': np.percentile(raw_scores, 10),
            'raw_score_p25': np.percentile(raw_scores, 25),
            'raw_score_p75': np.percentile(raw_scores, 75),
            'composite_mean': np.mean(composite_scores),
            'composite_median': np.median(composite_scores),
            'composite_std': np.std(composite_scores),
            'ranking_mean': np.mean([p.get('ranking_score', 0) for p in preds.values() if isinstance(p, dict)]),
            'trend_bonus_mean': np.mean(trend_bonus_vals) if trend_bonus_vals else 0,
            'trend_penalty_mean': np.mean(trend_penalty_vals) if trend_penalty_vals else 0,
            'price_slope_mean': np.mean(price_slopes) if price_slopes else 0,
            'price_slope_abs_mean': np.mean([abs(s) for s in price_slopes]) if price_slopes else 0,
            'price_r2_mean': np.mean(price_r_sq) if price_r_sq else 0,
            'buy_pct': sum(1 for p in preds.values() if isinstance(p, dict) and p.get('score', 0) > 0.30) / max(len(preds), 1) * 100,
            'rank_improvement_mean': np.mean(rank_imp) if rank_imp else 0,
            'rank_improvement_std': np.std(rank_imp) if rank_imp else 0,
            'rank_improvement_p90': np.percentile(rank_imp, 90) if rank_imp else 0,
        })

    # =====================================
    # 1. TIME SERIES: show key indicators month by month
    # =====================================
    print(f"\n{'='*100}")
    print(f"1. TIME SERIES OF KEY INDICATORS (Monthly Averages)")
    print(f"{'='*100}")
    print(f"  {'Date':8s} {'Regime':15s} {'#Stocks':8s} {'RawMean':10s} {'RawMed':10s} {'CompMean':10s} {'CompMed':10s} "
          f"{'PriceSlope':12s} {'Trend+':10s} {'Trend-':10s} {'RankImpP90':10s} {'Buy%':8s}")
    print(f"  {'-'*8} {'-'*15} {'-'*8} {'-'*10} {'-'*10} {'-'*10} {'-'*10} "
          f"{'-'*12} {'-'*10} {'-'*10} {'-'*10} {'-'*8}")

    monthly = defaultdict(list)
    for d in day_data:
        ym = d['date'][:6]
        monthly[ym].append(d)

    for ym in sorted(monthly.keys()):
        vals = monthly[ym]
        regime_counts = defaultdict(int)
        for v in vals:
            regime_counts[v['regime']] += 1
        dominant_regime = max(regime_counts, key=regime_counts.get)

        avg_n = np.mean([v['n_stocks_above_zero'] for v in vals])
        avg_raw_mean = np.mean([v['raw_score_mean'] for v in vals])
        avg_raw_med = np.mean([v['raw_score_median'] for v in vals])
        avg_comp_mean = np.mean([v['composite_mean'] for v in vals])
        avg_comp_med = np.mean([v['composite_median'] for v in vals])
        avg_slope = np.mean([v['price_slope_mean'] for v in vals])
        avg_tb = np.mean([v['trend_bonus_mean'] for v in vals])
        avg_tp = np.mean([v['trend_penalty_mean'] for v in vals])
        avg_rank_p90 = np.mean([v['rank_improvement_p90'] for v in vals])
        avg_buy_pct = np.mean([v['buy_pct'] for v in vals])

        regime_short = {'trending_up': '↑', 'sideways': '→', 'trending_down': '↓'}.get(dominant_regime, '?')
        print(f"  {ym:8s} {dominant_regime:15s} {avg_n:8.0f} {avg_raw_mean:>+9.4f} {avg_raw_med:>+9.4f} "
              f"{avg_comp_mean:>+9.4f} {avg_comp_med:>+9.4f} {avg_slope:>+10.4f} {avg_tb:>+9.4f} "
              f"{avg_tp:>+9.4f} {avg_rank_p90:>+9.4f} {avg_buy_pct:>7.2f}%")

    # =====================================
    # 2. CLASSIFICATION TEST: Can we predict sideways vs trending?
    # =====================================
    print(f"\n{'='*100}")
    print(f"2. CLASSIFICATION TEST: Can daily metrics predict market regime?")
    print(f"{'='*100}")

    # Prepare data
    X = []
    y = []
    for d in day_data:
        # Features for classification
        feat = [
            d['n_stocks_above_zero'],
            d['raw_score_mean'],
            d['raw_score_median'],
            d['raw_score_p25'],
            d['raw_score_p75'],
            d['composite_mean'],
            d['composite_median'],
            d['ranking_mean'],
            d['price_slope_mean'],
            d['price_slope_abs_mean'],
            d['trend_bonus_mean'],
            d['trend_penalty_mean'],
            d['buy_pct'],
            d['rank_improvement_p90'],
            d['rank_improvement_std'],
        ]
        X.append(feat)
        if d['regime'] == 'trending_up':
            y.append(1)
        elif d['regime'] == 'sideways':
            y.append(0)
        else:
            y.append(-1)

    # Simple threshold-based classifier: try each feature
    from sklearn.metrics import confusion_matrix

    feature_names = [
        '#Stocks>0', 'RawMean', 'RawMed', 'RawP25', 'RawP75',
        'CompMean', 'CompMed', 'RankMean', 'PriceSlope',
        '|PriceSlope|', 'Trend+', 'Trend-', 'Buy%', 'RankImpP90', 'RankImpStd'
    ]

    # For trending_up vs sideways (y=1 vs y=0)
    binary_x = [X[i] for i in range(len(y)) if y[i] in [0, 1]]
    binary_y = [y[i] for i in range(len(y)) if y[i] in [0, 1]]

    print(f"\n  Binary classification: sideways(0) vs trending_up(1)")
    print(f"  Total samples: {len(binary_y)}")
    print(f"  Sideways: {binary_y.count(0)}, Trending up: {binary_y.count(1)}")
    print()

    # Try each feature individually with a threshold
    for fi, fname in enumerate(feature_names):
        fvals = [v[fi] for v in binary_x]
        fyv = binary_y

        # Find best threshold by sweeping sorted unique values
        sorted_pairs = sorted(zip(fvals, fyv), key=lambda x: x[0])
        sorted_f = [p[0] for p in sorted_pairs]
        sorted_y = [p[1] for p in sorted_pairs]

        best_acc = 0
        best_th = 0
        for i in range(1, len(sorted_f)):
            if sorted_f[i] == sorted_f[i-1]:
                continue
            th = (sorted_f[i] + sorted_f[i-1]) / 2
            pred = [1 if f > th else 0 for f in sorted_f]
            acc = sum(1 for j in range(len(pred)) if pred[j] == sorted_y[j]) / len(pred)
            if acc > best_acc:
                best_acc = acc
                best_th = th

        # Also try predicting sideways (score BELOW threshold)
        best_acc2 = 0
        best_th2 = 0
        for i in range(1, len(sorted_f)):
            if sorted_f[i] == sorted_f[i-1]:
                continue
            th = (sorted_f[i] + sorted_f[i-1]) / 2
            # Reverse: score below th means sideways
            pred = [0 if f > th else 1 for f in sorted_f]
            acc = sum(1 for j in range(len(pred)) if pred[j] == sorted_y[j]) / len(pred)
            if acc > best_acc2:
                best_acc2 = acc
                best_th2 = th

        # Use whichever direction is better
        best_acc_final = max(best_acc, best_acc2)
        if best_acc_final == best_acc:
            direction = "high->trending"
        else:
            direction = "low->trending"
            best_th = best_th2

        # Baseline: always predict majority class
        majority = max(binary_y.count(0), binary_y.count(1))
        baseline_acc = majority / len(binary_y)

        sign = "↑" if best_acc_final > baseline_acc else "↓"
        print(f"  {fname:15s} best_th={best_th:>+.4f} acc={best_acc_final:.1%} (baseline={baseline_acc:.1%}) {sign}")

    # =====================================
    # 3. MULTI-FEATURE CLASSIFIER (Logistic Regression)
    # =====================================
    print(f"\n{'='*100}")
    print(f"3. LOGISTIC REGRESSION CLASSIFIER (all features)")
    print(f"{'='*100}")

    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import cross_val_score

    X_bin = np.array(binary_x)
    y_bin = np.array(binary_y)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_bin)

    lr = LogisticRegression(max_iter=1000, random_state=42)
    scores = cross_val_score(lr, X_scaled, y_bin, cv=5)
    print(f"  5-fold CV accuracy: {scores.mean():.1%} ± {scores.std():.1%}")

    # Full fit + feature coefficients
    lr.fit(X_scaled, y_bin)
    print(f"  Feature coefficients:")
    for name, coef in sorted(zip(feature_names, lr.coef_[0]), key=lambda x: -abs(x[1])):
        print(f"    {name:15s} coef={coef:>+.4f}")

    # =====================================
    # 4. ROLLING INDICATOR VISUALIZATION
    # =====================================
    print(f"\n{'='*100}")
    print(f"4. ROLLING 5-DAY TREND: 'Composite Mean - Ranking Mean' Crossover")
    print(f"(CompMean > RankMean → trending up, CompMean < RankMean → sideways/down)")
    print(f"{'='*100}")

    # The difference composite_mean - ranking_mean: in trending markets,
    # composite > ranking (scores are rising). In sideways, they're close.
    print(f"\n  {'Date':8s} {'Regime':15s} {'CompMean':10s} {'RankMean':10s} {'Diff':10s} {'Diff-5':10s} {'State':10s}")
    print(f"  {'-'*8} {'-'*15} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")

    # Also track rolling 5-day
    comp_means = [d['composite_mean'] for d in day_data]
    rank_means = [d['ranking_mean'] for d in day_data]
    diffs = [comp_means[i] - rank_means[i] for i in range(len(day_data))]

    # Running 5-day average of diff
    diff_ma5 = []
    for i in range(len(diffs)):
        if i < 4:
            diff_ma5.append(diffs[i])
        else:
            diff_ma5.append(np.mean(diffs[i-4:i+1]))

    # Show at month boundaries and regime transitions
    last_ym = ""
    regime_shifts = []
    prev_regime = None
    for i, d in enumerate(day_data):
        ym = d['date'][:6]

        # Detect regime shift
        if prev_regime is not None and d['regime'] != prev_regime:
            regime_shifts.append((i, d['date'], prev_regime, d['regime']))
        prev_regime = d['regime']

        # Print every month start
        if ym != last_ym:
            sign = "+" if diffs[i] > 0 else "-"
            state = "trending" if diff_ma5[i] > 0.02 else ("sideways" if abs(diff_ma5[i]) <= 0.02 else "declining")
            print(f"  {d['date']:8s} {d['regime']:15s} {comp_means[i]:>+9.4f} {rank_means[i]:>+9.4f} "
                  f"{diffs[i]:>+9.4f} {diff_ma5[i]:>+9.4f} {state:10s}")
            last_ym = ym

    # Print regime transitions
    print(f"\n  Regime transitions detected:")
    for i, date, old_r, new_r in regime_shifts:
        # Show indicator 3 days before and after
        context = []
        for offset in [-3, -2, -1, 0, 1, 2, 3]:
            idx = max(0, min(len(day_data)-1, i + offset))
            cm = comp_means[idx]
            rm = rank_means[idx]
            dm = diff_ma5[idx]
            context.append(f"{day_data[idx]['date']}(diff={dm:+.3f})")
        print(f"  {date}: {old_r} → {new_r}")
        print(f"    Context: {' → '.join(context)}")

    # =====================================
    # 5. FINAL RECOMMENDATION: Which indicator works best?
    # =====================================
    print(f"\n{'='*100}")
    print(f"5. COMPOSITE SIGNAL: Best practical market state indicator")
    print(f"{'='*100}")

    # Check: what happens when we use 3 sign rules:
    # Rule A: ranking_mean > 0.04 (trending)
    # Rule B: raw_score_mean > 0.175 (trending)
    # Rule C: composite_mean > ranking_mean (rising, not falling)
    rules = {
        'ranking_mean>0.04': lambda d: d['ranking_mean'] > 0.04,
        'raw_score_mean>0.175': lambda d: d['raw_score_mean'] > 0.175,
        'composite>ranking': lambda d: d['composite_mean'] > d['ranking_mean'],
        'n_stocks>55': lambda d: d['n_stocks_above_zero'] > 55,
        'price_slope>0.15': lambda d: d['price_slope_mean'] > 0.15,
        'trend_bonus>0.005': lambda d: d['trend_bonus_mean'] > 0.005,
        'buy_pct>5%': lambda d: d['buy_pct'] > 5,
    }

    for name, rule in rules.items():
        correct_trending = 0
        correct_sideways = 0
        total_trending = 0
        total_sideways = 0
        false_pos = 0
        false_neg = 0
        for d in day_data:
            pred_trending = rule(d)
            if d['regime'] == 'trending_up':
                total_trending += 1
                if pred_trending:
                    correct_trending += 1
                else:
                    false_neg += 1
            elif d['regime'] == 'sideways':
                total_sideways += 1
                if not pred_trending:
                    correct_sideways += 1
                else:
                    false_pos += 1

        if total_trending + total_sideways > 0:
            acc_trending = correct_trending / total_trending if total_trending > 0 else 0
            acc_sideways = correct_sideways / total_sideways if total_sideways > 0 else 0
            overall = (correct_trending + correct_sideways) / max(total_trending + total_sideways, 1)
            print(f"\n  {name:25s} overall={overall:.0%} "
                  f"trending_recall={acc_trending:.0%} sideways_recall={acc_sideways:.0%} "
                  f"FP={false_pos} FN={false_neg}")

    # Now try a composite rule: 3-out-of-5
    def composite_rule(d):
        votes = 0
        if d['ranking_mean'] > 0.04: votes += 1
        if d['raw_score_mean'] > 0.175: votes += 1
        if d['composite_mean'] > d['ranking_mean']: votes += 1
        if d['n_stocks_above_zero'] > 55: votes += 1
        if d['price_slope_mean'] > 0.15: votes += 1
        return votes >= 3

    correct_trending = sum(1 for d in day_data if d['regime']=='trending_up' and composite_rule(d))
    correct_sideways = sum(1 for d in day_data if d['regime']=='sideways' and not composite_rule(d))
    total_trending = sum(1 for d in day_data if d['regime']=='trending_up')
    total_sideways = sum(1 for d in day_data if d['regime']=='sideways')
    fp = sum(1 for d in day_data if d['regime']=='sideways' and composite_rule(d))
    fn = sum(1 for d in day_data if d['regime']=='trending_up' and not composite_rule(d))

    print(f"\n  {'COMPOSITE(3/5)':25s} overall={(correct_trending+correct_sideways)/max(total_trending+total_sideways,1):.0%} "
          f"trending_recall={correct_trending/max(total_trending,1):.0%} sideways_recall={correct_sideways/max(total_sideways,1):.0%} "
          f"FP={fp} FN={fn}")

    # Check: what % of the worst months are correctly classified?
    print(f"\n  --- Checking specific problematic periods ---")
    for ym in ['202504', '202505', '202512']:
        month_vals = [d for d in day_data if d['date'][:6] == ym]
        if month_vals:
            signal_strength = []
            for d in month_vals:
                votes = 0
                if d['ranking_mean'] > 0.04: votes += 1
                if d['raw_score_mean'] > 0.175: votes += 1
                if d['composite_mean'] > d['ranking_mean']: votes += 1
                if d['n_stocks_above_zero'] > 55: votes += 1
                if d['price_slope_mean'] > 0.15: votes += 1
                signal_strength.append(votes)
            avg_signal = np.mean(signal_strength)
            side_classified = sum(1 for v in signal_strength if v < 3)
            print(f"  {ym}: avg_composite_signal={avg_signal:.1f}/5, "
                  f"classified_as_sideways={side_classified}/{len(month_vals)} days")

asyncio.run(main())
