"""Comprehensive backtest analysis script.

Queries ALL backtest records from MongoDB and performs detailed analysis:
  - Trade-by-trade analysis (entry/exit, holding periods, P&L)
  - Position sizing analysis
  - Cash management analysis
  - Market timing analysis
  - Chain reaction detection
  - Drawdown analysis
  - Win rate and risk/reward per trade
"""

import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from dotenv import load_dotenv
load_dotenv()

import asyncio
from bson.objectid import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient


# ---------------------------------------------------------------------------
# MongoDB connection
# ---------------------------------------------------------------------------

async def get_db():
    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGODB_DB", "trade_alpha")
    client = AsyncIOMotorClient(uri)
    return client[db_name], client


# ---------------------------------------------------------------------------
# Number formatting helpers
# ---------------------------------------------------------------------------

def fmt(val, decimals=2):
    """Format a number with commas and decimals."""
    if val is None:
        return "N/A"
    if isinstance(val, float):
        return f"{val:,.{decimals}f}"
    return str(val)


def fmt_pct(val, decimals=2):
    """Format as percentage."""
    if val is None:
        return "N/A"
    return f"{val * 100:,.{decimals}f}%"


def fmt_date(d):
    return str(d) if d else "N/A"


# ---------------------------------------------------------------------------
# Analysis functions
# ---------------------------------------------------------------------------

def analyze_trades(trades, backtest):
    """Trade-by-trade analysis: group buy/sell pairs, compute P&L."""
    if not trades:
        return []

    # Sort trades by date
    sorted_trades = sorted(trades, key=lambda t: t.get("trade_date", ""))

    # Group by ts_code
    by_stock = defaultdict(list)
    for t in sorted_trades:
        by_stock[t["ts_code"]].append(t)

    results = []
    for ts_code, stock_trades in sorted(by_stock.items()):
        buys = [t for t in stock_trades if t.get("action") == "buy"]
        sells = [t for t in stock_trades if t.get("action") == "sell"]

        # Pair buys and sells
        pairs = []
        buy_idx = 0
        for sell in sells:
            if buy_idx < len(buys):
                buy = buys[buy_idx]
                buy_idx += 1
                pairs.append((buy, sell))

        total_pnl = 0.0
        total_fees = 0.0
        win_count = 0
        loss_count = 0
        holding_periods = []

        for buy, sell in pairs:
            pnl = sell.get("pnl_amount") or 0.0
            total_pnl += pnl
            total_fees += buy.get("fee", 0.0) + sell.get("fee", 0.0)
            if pnl > 0:
                win_count += 1
            else:
                loss_count += 1

            # Holding period
            try:
                bd = datetime.strptime(buy["trade_date"], "%Y%m%d")
                sd = datetime.strptime(sell["trade_date"], "%Y%m%d")
                hold_days = (sd - bd).days
            except (ValueError, KeyError):
                hold_days = 0
            if hold_days > 0:
                holding_periods.append(hold_days)

            results.append({
                "ts_code": ts_code,
                "buy_date": buy["trade_date"],
                "buy_price": buy.get("filled_price", 0),
                "buy_shares": buy.get("shares", 0),
                "sell_date": sell["trade_date"],
                "sell_price": sell.get("filled_price", 0),
                "pnl": pnl,
                "pnl_pct": sell.get("pnl_pct", 0),
                "hold_days": hold_days,
                "sell_reason": sell.get("reason", ""),
            })

    return results


def analyze_positions(daily_snapshots):
    """Analyze position sizing over time."""
    if not daily_snapshots:
        return []

    sorted_snaps = sorted(daily_snapshots, key=lambda s: s.get("date", ""))
    analysis = []
    for snap in sorted_snaps:
        positions = snap.get("positions", [])
        total_value = snap.get("total_value", 0) or 1  # avoid div by zero
        cash = snap.get("cash", 0)
        cash_ratio = cash / total_value if total_value > 0 else 1.0

        pos_info = []
        for p in positions:
            market_val = p.get("shares", 0) * (p.get("buy_price", 0))
            pos_info.append({
                "ts_code": p.get("ts_code", ""),
                "pct": market_val / total_value if total_value > 0 else 0,
            })

        analysis.append({
            "date": snap["date"],
            "cash_ratio": cash_ratio,
            "num_positions": len(positions),
            "positions": pos_info,
        })
    return analysis


def analyze_cash(daily_snapshots):
    """Analyze cash management patterns."""
    if not daily_snapshots:
        return []

    sorted_snaps = sorted(daily_snapshots, key=lambda s: s.get("date", ""))
    cash_ratios = []
    for snap in sorted_snaps:
        total_value = snap.get("total_value", 0) or 1
        cash_ratio = snap.get("cash", 0) / total_value
        cash_ratios.append({
            "date": snap["date"],
            "cash": snap.get("cash", 0),
            "total_value": snap.get("total_value", 0),
            "cash_ratio": cash_ratio,
        })
    return cash_ratios


def analyze_drawdown(daily_snapshots):
    """Max drawdown and recovery analysis."""
    sorted_snaps = sorted(daily_snapshots, key=lambda s: s.get("date", ""))
    if not sorted_snaps:
        return None, []

    peak = 0.0
    peak_date = ""
    max_dd = 0.0
    max_dd_start = ""
    max_dd_end = ""
    current_dd = 0.0
    current_dd_start = ""
    in_dd = False

    drawdowns = []
    for snap in sorted_snaps:
        val = snap.get("total_value", 0)
        date = snap.get("date", "")

        if val > peak:
            peak = val
            peak_date = date
            if in_dd:
                # recovery
                drawdowns.append({
                    "start": current_dd_start,
                    "end": date,
                    "max_dd": current_dd,
                })
                in_dd = False
                current_dd = 0.0
        else:
            dd = (peak - val) / peak if peak > 0 else 0
            if dd > current_dd:
                current_dd = dd
                if not in_dd:
                    current_dd_start = date
                    in_dd = True
            if dd > max_dd:
                max_dd = dd
                max_dd_start = current_dd_start if current_dd_start else date
                max_dd_end = date

    # Record final drawdown if still in one
    if in_dd:
        drawdowns.append({
            "start": current_dd_start,
            "end": sorted_snaps[-1]["date"],
            "max_dd": current_dd,
        })

    max_dd_info = {
        "max_drawdown": max_dd,
        "start_date": max_dd_start,
        "end_date": max_dd_end,
    }
    return max_dd_info, drawdowns


def compute_win_rate(trade_analysis):
    """Compute win rate and risk/reward from trade analysis."""
    if not trade_analysis:
        return {}

    wins = [t for t in trade_analysis if t["pnl"] > 0]
    losses = [t for t in trade_analysis if t["pnl"] <= 0]
    total = len(wins) + len(losses)

    if total == 0:
        return {}

    win_rate = len(wins) / total
    avg_win = sum(t["pnl"] for t in wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(t["pnl"] for t in losses)) / len(losses) if losses else 0.0
    profit_factor = sum(t["pnl"] for t in wins) / abs(sum(t["pnl"] for t in losses)) if losses and sum(t["pnl"] for t in losses) != 0 else float("inf")
    avg_hold = sum(t["hold_days"] for t in trade_analysis) / len(trade_analysis) if trade_analysis else 0
    total_pnl = sum(t["pnl"] for t in trade_analysis)

    return {
        "total_trades": total,
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "avg_hold_days": avg_hold,
        "total_pnl": total_pnl,
    }


def detect_chain_reactions(trades):
    """Detect chain reactions: how closing one position freed cash for another."""
    sorted_trades = sorted(trades, key=lambda t: t.get("trade_date", ""))
    if not sorted_trades:
        return []

    chains = []
    recent_sells = []

    for t in sorted_trades:
        if t.get("action") == "sell":
            recent_sells.append(t)
            # Keep last 5 sells
            if len(recent_sells) > 5:
                recent_sells.pop(0)
        elif t.get("action") == "buy":
            # Check if a recent sell freed cash for this buy
            buy_date = t.get("trade_date", "")
            for sell in recent_sells:
                sell_date = sell.get("trade_date", "")
                try:
                    sd = datetime.strptime(sell_date, "%Y%m%d")
                    bd = datetime.strptime(buy_date, "%Y%m%d")
                    days_diff = (bd - sd).days
                except (ValueError, KeyError):
                    days_diff = 999
                if 0 <= days_diff <= 3:
                    pnl = sell.get("pnl_amount", 0) or 0
                    chains.append({
                        "sell_code": sell.get("ts_code", ""),
                        "sell_date": sell_date,
                        "sell_pnl": pnl,
                        "buy_code": t.get("ts_code", ""),
                        "buy_date": buy_date,
                        "gap_days": days_diff,
                    })
                    break  # only link to nearest sell
    return chains


def analyze_market_timing(daily_snapshots, trades):
    """Analyze entry/exit decisions around market regime changes."""
    sorted_snaps = sorted(daily_snapshots, key=lambda s: s.get("date", ""))
    if not sorted_snaps:
        return []

    # Map date -> regime
    regime_map = {}
    for snap in sorted_snaps:
        regime_map[snap["date"]] = snap.get("ranking_regime", "")

    timing_analysis = []
    for t in trades:
        trade_date = t.get("trade_date", "")
        regime = regime_map.get(trade_date, "unknown")
        action = t.get("action", "")
        ts_code = t.get("ts_code", "")

        timing_analysis.append({
            "date": trade_date,
            "action": action,
            "ts_code": ts_code,
            "regime": regime,
            "reason": t.get("reason", ""),
        })
    return timing_analysis


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

async def analyze_all(limit: int = 20):
    db, client = await get_db()

    print("=" * 120)
    print("  TRADE-ALPHA: COMPREHENSIVE BACKTEST ANALYSIS REPORT")
    print("=" * 120)
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Database:  {os.getenv('MONGODB_DB', 'trade_alpha')}")
    print()

    # -----------------------------------------------------------------------
    # 1. Fetch all backtest records
    # -----------------------------------------------------------------------
    total_count = await db["execution_results"].count_documents({})
    backtests = await db["execution_results"].find().sort("created_at", -1).limit(limit).to_list(length=None)
    print(f"  Total backtest records in DB: {total_count}")
    print(f"  Showing top {len(backtests)} most recent records")
    print()

    if not backtests:
        print("  No backtest records to analyze.")
        client.close()
        return

    for bt_idx, bt in enumerate(backtests, 1):
        bt_id = str(bt["_id"])
        bt_oid = ObjectId(bt_id)
        bt_name = bt.get("name", "Unnamed")
        print(f"\n  [Processing backtest {bt_idx}/{len(backtests)}]", end="", flush=True)
        print(f"{'=' * 120}")
        print(f"  BACKTEST #{bt_idx}: {bt_name}")
        print(f"{'=' * 120}")
        print(f"  ID:             {bt_id}")
        print(f"  Mode:           {bt.get('mode', 'N/A')}")
        print(f"  Period:         {fmt_date(bt.get('start_date'))} → {fmt_date(bt.get('end_date'))}")
        print(f"  Initial Capital: {fmt(bt.get('initial_capital'))}")
        print(f"  Final Value:    {fmt(bt.get('final_value'))}")
        print(f"  Total Return:   {fmt_pct(bt.get('total_return'))}")
        print(f"  Annual Return:  {fmt_pct(bt.get('annual_return'))}")
        print(f"  Max Drawdown:   {fmt_pct(bt.get('max_drawdown'))}")
        print(f"  Sharpe Ratio:   {fmt(bt.get('sharpe_ratio'), 4)}")
        print(f"  Volatility:     {fmt_pct(bt.get('volatility'))}")
        print(f"  Win Rate:       {fmt_pct(bt.get('win_rate'))}")
        print(f"  Total Trades:   {bt.get('total_trades', 0)}")
        print(f"  Total Fees:     {fmt(bt.get('total_fees'))}")
        print(f"  Status:         {bt.get('status', 'N/A')}")
        print()

        # Baseline comparison
        baseline_return = bt.get("baseline_return")
        if baseline_return is not None:
            print(f"  --- Baseline Comparison ---")
            print(f"  Baseline Return:     {fmt_pct(baseline_return)}")
            print(f"  Excess Return:       {fmt_pct(bt.get('excess_return'))}")
            print(f"  Baseline Max DD:     {fmt_pct(bt.get('baseline_max_drawdown'))}")
            print(f"  Baseline Ann Return: {fmt_pct(bt.get('baseline_annual_return'))}")
            print(f"  Baseline Sharpe:     {fmt(bt.get('baseline_sharpe_ratio'), 4)}")
            print()

        # Strategy snapshot
        strategy_snap = bt.get("strategy_snapshot")
        if strategy_snap:
            print(f"  --- Strategy Config ---")
            print(f"  Name:              {strategy_snap.get('name', 'N/A')}")
            print(f"  Type:              {strategy_snap.get('type', 'N/A')}")
            print(f"  Max Positions:     {strategy_snap.get('max_positions', 'N/A')}")
            print(f"  Max Position %:    {fmt_pct(strategy_snap.get('max_position_pct')) if strategy_snap.get('max_position_pct') else 'N/A'}")
            print(f"  Min Order Value:   {fmt(strategy_snap.get('min_order_value'))}")
            print(f"  Buy Threshold:     {fmt_pct(strategy_snap.get('buy_threshold'))}")
            print(f"  Sell Threshold:    {fmt_pct(strategy_snap.get('sell_threshold'))}")
            print(f"  Min Hold Days:     {strategy_snap.get('min_hold_days', 'N/A')}")
            print(f"  Max Hold Days:     {strategy_snap.get('max_hold_days', 'N/A')}")
            print(f"  Stop Loss %:       {fmt_pct(strategy_snap.get('stop_loss_pct'))}")
            print(f"  Use Phase Strategy:  {strategy_snap.get('use_phase_strategy', True)}")
            print(f"  Use Momentum:      {strategy_snap.get('use_momentum_boost', False)}")
            print(f"  Use Trend Bonus:   {strategy_snap.get('use_trend_bonus', False)}")
            print()

        # Model snapshot
        model_snap = bt.get("model_snapshot")
        if model_snap:
            print(f"  --- Model Config ---")
            print(f"  Name:              {model_snap.get('name', 'N/A')}")
            print(f"  Model Type:        {model_snap.get('model_type', 'N/A')}")
            print(f"  Feature Fields:    {len(model_snap.get('feature_fields', []))}")
            print(f"  Horizons:          {model_snap.get('classification_horizons', [])}")
            print()

        # -----------------------------------------------------------------------
        # 2. Fetch trades
        # -----------------------------------------------------------------------
        trades = await db["execution_trades"].find({"backtest_id": bt_id}).sort("trade_date", 1).to_list(length=None)
        print(f"  --- Trade Logs ({len(trades)} total) ---")
        print()

        if trades:
            # Group by month
            monthly_counts = defaultdict(int)
            for t in trades:
                d = t.get("trade_date", "")
                monthly_counts[d[:6]] += 1

            print(f"  Trade activity by month:")
            for month in sorted(monthly_counts.keys()):
                print(f"    {month[:4]}-{month[4:]}: {monthly_counts[month]} trades")
            print()

            # Trade-by-trade detail
            trade_analysis = analyze_trades(trades, bt)
            if trade_analysis:
                print(f"  --- Trade-by-Trade P&L Analysis ---")
                print(f"  {'Ts Code':<12} {'Buy Date':<10} {'Buy Price':<10} {'Sell Date':<10} {'Sell Price':<10} {'Shares':<8} {'P&L':<10} {'P&L%':<8} {'Hold Days':<10} {'Reason'}")
                print(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*10} {'-'*8} {'-'*10} {'-'*30}")
                for ta in trade_analysis:
                    print(f"  {ta['ts_code']:<12} {ta['buy_date']:<10} {fmt(ta['buy_price']):<10} {ta['sell_date']:<10} {fmt(ta['sell_price']):<10} {ta['buy_shares']:<8} {fmt(ta['pnl']):<10} {fmt_pct(ta['pnl_pct']):<8} {ta['hold_days']:<10} {ta['sell_reason'][:30]}")
                print()

                # Win rate stats
                wr = compute_win_rate(trade_analysis)
                if wr:
                    print(f"  --- Win Rate & Risk/Reward ---")
                    print(f"  Total Trades:    {wr['total_trades']}")
                    print(f"  Winning Trades:  {wr['win_count']} ({wr['win_count']/wr['total_trades']*100:.1f}%)")
                    print(f"  Losing Trades:   {wr['loss_count']} ({wr['loss_count']/wr['total_trades']*100:.1f}%)")
                    print(f"  Win Rate:        {wr['win_rate']*100:.1f}%")
                    print(f"  Avg Win:         {fmt(wr['avg_win'])}")
                    print(f"  Avg Loss:        {fmt(wr['avg_loss'])}")
                    print(f"  Profit Factor:   {fmt(wr['profit_factor'], 2)}")
                    print(f"  Avg Hold Days:   {wr['avg_hold_days']:.1f}")
                    print(f"  Total P&L:       {fmt(wr['total_pnl'])}")
                    print()

                # Chain reaction detection
                chains = detect_chain_reactions(trades)
                if chains:
                    print(f"  --- Chain Reaction Detection (Sell → Buy within 3 days) ---")
                    print(f"  {'Sell Stock':<12} {'Sell Date':<10} {'Sell P&L':<10} {'→ Buy Stock':<12} {'Buy Date':<10} {'Gap Days':<10}")
                    print(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*12} {'-'*10} {'-'*10}")
                    for ch in chains:
                        print(f"  {ch['sell_code']:<12} {ch['sell_date']:<10} {fmt(ch['sell_pnl']):<10} {ch['buy_code']:<12} {ch['buy_date']:<10} {ch['gap_days']:<10}")
                    print()

        else:
            print("  No trade records found.")
            print()

        # -----------------------------------------------------------------------
        # 3. Fetch daily snapshots
        # -----------------------------------------------------------------------
        snapshots = await db["execution_daily_snapshots"].find({"backtest_id": bt_oid}).sort("date", 1).to_list(length=None)
        print(f"  --- Daily Snapshots ({len(snapshots)} days) ---")
        print()

        if snapshots:
            first_snap = snapshots[0]
            last_snap = snapshots[-1]

            # First and last day summary
            print(f"  Period:         {first_snap.get('date', 'N/A')} → {last_snap.get('date', 'N/A')}")
            print(f"  Start Value:    {fmt(first_snap.get('total_value'))}")
            print(f"  End Value:      {fmt(last_snap.get('total_value'))}")
            print(f"  Start Cash:     {fmt(first_snap.get('cash'))}")
            print(f"  End Cash:       {fmt(last_snap.get('cash'))}")
            print()

            # Position sizing analysis
            pos_analysis = analyze_positions(snapshots)
            if pos_analysis:
                print(f"  --- Position Sizing Over Time ---")
                print(f"  {'Date':<10} {'#Pos':<6} {'Cash%':<8} {'Positions (code:pct)'}")
                print(f"  {'-'*10} {'-'*6} {'-'*8} {'-'*60}")
                for pa in pos_analysis:
                    pos_str = ", ".join([f"{p['ts_code']}:{p['pct']*100:.1f}%" for p in pa["positions"][:5]])
                    if len(pa["positions"]) > 5:
                        pos_str += f" ... (+{len(pa['positions'])-5} more)"
                    print(f"  {pa['date']:<10} {pa['num_positions']:<6} {pa['cash_ratio']*100:<8.1f}% {pos_str}")
                print()

            # Cash management
            cash_analysis = analyze_cash(snapshots)
            if cash_analysis:
                print(f"  --- Cash Management Analysis ---")
                print(f"  {'Date':<10} {'Cash':<12} {'Total Value':<12} {'Cash Ratio':<12}")
                print(f"  {'-'*10} {'-'*12} {'-'*12} {'-'*12}")
                for ca in cash_analysis:
                    print(f"  {ca['date']:<10} {fmt(ca['cash']):<12} {fmt(ca['total_value']):<12} {ca['cash_ratio']*100:<12.1f}%")
                print()

                # Idle cash analysis
                cash_ratios = [c["cash_ratio"] for c in cash_analysis]
                avg_cash_ratio = sum(cash_ratios) / len(cash_ratios) if cash_ratios else 0
                max_cash_ratio = max(cash_ratios) if cash_ratios else 0
                min_cash_ratio = min(cash_ratios) if cash_ratios else 0

                total_days = len(cash_analysis)
                high_cash_days = sum(1 for c in cash_ratios if c > 0.5)
                print(f"  --- Idle Cash Summary ---")
                print(f"  Avg Cash Ratio:  {avg_cash_ratio*100:.1f}%")
                print(f"  Max Cash Ratio:  {max_cash_ratio*100:.1f}%")
                print(f"  Min Cash Ratio:  {min_cash_ratio*100:.1f}%")
                print(f"  Days >50% Cash:  {high_cash_days}/{total_days} ({high_cash_days/total_days*100:.1f}%)")
                print()

            # Drawdown analysis
            max_dd_info, drawdowns = analyze_drawdown(snapshots)
            if max_dd_info:
                print(f"  --- Drawdown Analysis ---")
                print(f"  Max Drawdown:     {fmt_pct(max_dd_info['max_drawdown'])}")
                print(f"  Drawdown Start:   {max_dd_info['start_date']}")
                print(f"  Drawdown End:     {max_dd_info['end_date']}")
                print()

                if drawdowns:
                    print(f"  All Drawdown Events (>1%):")
                    significant_dds = [d for d in drawdowns if d["max_dd"] > 0.01]
                    if significant_dds:
                        print(f"  {'Start':<10} {'End':<10} {'Max DD':<10}")
                        print(f"  {'-'*10} {'-'*10} {'-'*10}")
                        for dd in significant_dds:
                            print(f"  {dd['start']:<10} {dd['end']:<10} {fmt_pct(dd['max_dd']):<10}")
                        print()

            # Market timing
            timing = analyze_market_timing(snapshots, trades)
            if timing:
                print(f"  --- Market Timing Analysis ---")
                regimes_seen = defaultdict(lambda: {"buys": 0, "sells": 0})
                for tm in timing:
                    r = tm["regime"] or "unknown"
                    if tm["action"] == "buy":
                        regimes_seen[r]["buys"] += 1
                    elif tm["action"] == "sell":
                        regimes_seen[r]["sells"] += 1

                print(f"  Trade distribution by market regime:")
                print(f"  {'Regime':<20} {'Buys':<8} {'Sells':<8} {'Total':<8}")
                print(f"  {'-'*20} {'-'*8} {'-'*8} {'-'*8}")
                for regime, counts in sorted(regimes_seen.items()):
                    total_r = counts["buys"] + counts["sells"]
                    print(f"  {regime:<20} {counts['buys']:<8} {counts['sells']:<8} {total_r:<8}")
                print()

            # Day-by-day return summary
            daily_returns = [s.get("day_return", 0) or 0 for s in snapshots]
            if daily_returns:
                positive_days = sum(1 for r in daily_returns if r > 0)
                negative_days = sum(1 for r in daily_returns if r < 0)
                zero_days = sum(1 for r in daily_returns if r == 0)
                avg_daily_return = sum(daily_returns) / len(daily_returns) if daily_returns else 0
                best_day = max(daily_returns) if daily_returns else 0
                worst_day = min(daily_returns) if daily_returns else 0

                print(f"  --- Daily Return Summary ---")
                print(f"  Positive Days:    {positive_days} ({positive_days/len(daily_returns)*100:.1f}%)")
                print(f"  Negative Days:    {negative_days} ({negative_days/len(daily_returns)*100:.1f}%)")
                print(f"  Flat Days:        {zero_days} ({zero_days/len(daily_returns)*100:.1f}%)")
                print(f"  Avg Daily Return: {fmt_pct(avg_daily_return)}")
                print(f"  Best Day:         {fmt_pct(best_day)}")
                print(f"  Worst Day:        {fmt_pct(worst_day)}")
                print()

        else:
            print("  No daily snapshots found.")
            print()

        # -----------------------------------------------------------------------
        # Summary row
        # -----------------------------------------------------------------------
        print(f"  {'─' * 120}")
        print(f"  End of analysis for backtest #{bt_idx}: {bt_name}")
        print()

    client.close()


if __name__ == "__main__":
    import sys
    out_file = None
    if len(sys.argv) > 1 and sys.argv[1] == "--output":
        out_file = sys.argv[2]
    
    if out_file:
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            asyncio.run(analyze_all())
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(buf.getvalue())
        print(f"Analysis written to {out_file}")
    else:
        asyncio.run(analyze_all())