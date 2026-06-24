"""Analyze rank_improvement and ranking_score distribution from real backtest data."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from dotenv import load_dotenv
load_dotenv()
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from trade_alpha.config import load_config
from collections import Counter
import math

async def main():
    cfg = load_config()
    client = AsyncIOMotorClient(cfg.mongodb_uri)
    db = client[cfg.mongodb_db]

    bt_name = "backtest_lstm_202606241707"
    r = await db.execution_results.find_one({"name": bt_name})
    bt_id = r["_id"]

    # Get all daily snapshots to see scored stocks
    snaps = await db.execution_daily_snapshots.find(
        {"backtest_id": bt_id}
    ).sort("date").to_list(2000)
    
    # Sample: collect ranking_score and compute rank_improvement from predictions
    all_scores = []
    all_rank_imps = []
    all_composites = []
    
    sample_count = 0
    for s in snaps:
        predictions = s.get("predictions", {}) or {}
        for ts_code, pred in predictions.items():
            ranking_score = pred.get("ranking_score")
            composite_score = pred.get("composite_score")
            if ranking_score is not None:
                all_scores.append(ranking_score)
                all_composites.append(composite_score if composite_score is not None else 0)
        sample_count += 1
        if sample_count >= 200:  # sample ~200 days
            break
    
    if all_scores:
        print(f"=== ranking_score distribution (sample: {len(all_scores)} points) ===")
        all_scores.sort()
        print(f"  min: {all_scores[0]:.4f}")
        print(f"  1%:  {all_scores[len(all_scores)//100]:.4f}")
        print(f"  5%:  {all_scores[len(all_scores)//20]:.4f}")
        print(f"  25%: {all_scores[len(all_scores)//4]:.4f}")
        print(f"  50%: {all_scores[len(all_scores)//2]:.4f}")
        print(f"  75%: {all_scores[3*len(all_scores)//4]:.4f}")
        print(f"  95%: {all_scores[19*len(all_scores)//20]:.4f}")
        print(f"  99%: {all_scores[99*len(all_scores)//100]:.4f}")
        print(f"  max: {all_scores[-1]:.4f}")
        print(f"  mean: {sum(all_scores)/len(all_scores):.4f}")
        print(f"  std: {math.sqrt(sum((x-sum(all_scores)/len(all_scores))**2 for x in all_scores)/len(all_scores)):.4f}")

    if all_composites:
        print(f"\n=== composite_score distribution ===")
        all_composites.sort()
        print(f"  min: {all_composites[0]:.4f}")
        print(f"  5%:  {all_composites[len(all_composites)//20]:.4f}")
        print(f"  50%: {all_composites[len(all_composites)//2]:.4f}")
        print(f"  95%: {all_composites[19*len(all_composites)//20]:.4f}")
        print(f"  max: {all_composites[-1]:.4f}")
        print(f"  mean: {sum(all_composites)/len(all_composites):.4f}")

    # Now get rank_improvement from the ScoringHistory or trades
    # rank_improvement is computed from rank_history in MarketRegimeAnalyzer
    # Let's look at execution_trades to see buy-side rank_improvement values
    trades = await db.execution_trades.find({"backtest_id": bt_id}).to_list(10000)
    buy_trades = [t for t in trades if t.get("action") == "buy" and t.get("status") == "filled"]
    
    # Check if rank_improvement is stored in the trade record
    has_ri = [t.get("rank_improvement") for t in buy_trades if t.get("rank_improvement") is not None]
    has_entry_score = [t.get("entry_score") for t in buy_trades if t.get("entry_score") is not None]
    
    print(f"\n=== Trade data ===")
    print(f"  Filled buys with rank_improvement: {len(has_ri)}")
    if has_ri:
        has_ri.sort()
        print(f"  min: {has_ri[0]:.4f}")
        print(f"  25%: {has_ri[len(has_ri)//4]:.4f}")
        print(f"  50%: {has_ri[len(has_ri)//2]:.4f}")
        print(f"  75%: {has_ri[3*len(has_ri)//4]:.4f}")
        print(f"  95%: {has_ri[19*len(has_ri)//20]:.4f}")
        print(f"  max: {has_ri[-1]:.4f}")
        print(f"  mean: {sum(has_ri)/len(has_ri):.4f}")
    
    if has_entry_score:
        has_entry_score.sort()
        print(f"\n  entry_score distribution:")
        print(f"  min: {has_entry_score[0]:.4f}")
        print(f"  25%: {has_entry_score[len(has_entry_score)//4]:.4f}")
        print(f"  50%: {has_entry_score[len(has_entry_score)//2]:.4f}")
        print(f"  75%: {has_entry_score[3*len(has_entry_score)//4]:.4f}")
        print(f"  max: {has_entry_score[-1]:.4f}")
        print(f"  mean: {sum(has_entry_score)/len(has_entry_score):.4f}")

    # Let's also look at some specific days to see the actual rank_improvement values
    # by looking at a few daily snapshots' position data
    print(f"\n=== Sample daily snapshots position scores ===")
    daily_count = 0
    for s in snaps:
        positions = s.get("positions", []) or []
        if positions:
            entry_scores = [p.get("entry_score", 0) for p in positions]
            print(f"  {s['date']}: {len(positions)} positions, "
                  f"entry_scores={[f'{x:.3f}' for x in entry_scores[:5]]}")
            daily_count += 1
            if daily_count >= 5:
                break

    client.close()

asyncio.run(main())
