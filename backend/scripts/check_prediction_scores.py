"""Check prediction scores from the latest backtest snapshots."""
import asyncio
from trade_alpha.dao import init_db, ExecutionDailySnapshot


async def check(ts_code: str = "002594.SZ"):
    await init_db()

    snapshots = await ExecutionDailySnapshot.find().sort(ExecutionDailySnapshot.date).to_list()

    print(f"Total snapshots: {len(snapshots)}")
    print(f"Date range: {snapshots[0].date if snapshots else 'N/A'} ~ {snapshots[-1].date if snapshots else 'N/A'}")

    scores = []
    for s in snapshots:
        if ts_code in s.predictions:
            pred = s.predictions[ts_code]
            score = pred.get("score", 0)
            prob_3d = pred.get("up_prob_3d", 0)
            prob_5d = pred.get("up_prob_5d", 0)
            scores.append((s.date, score, prob_3d, prob_5d))

    print(f"\n{ts_code} prediction records: {len(scores)}")
    print(f"Score range: {min(s[1] for s in scores):.4f} ~ {max(s[1] for s in scores):.4f}")
    pos = sum(1 for s in scores if s[1] > 0)
    neg = sum(1 for s in scores if s[1] <= 0)
    print(f"Score > 0: {pos}, Score <= 0: {neg}")

    print(f"\nFirst 10:")
    for date, score, p3, p5 in scores[:10]:
        print(f"  {date}: score={score:.4f} up_prob_3d={p3:.4f} up_prob_5d={p5:.4f}")

    print(f"\nLast 10:")
    for date, score, p3, p5 in scores[-10:]:
        print(f"  {date}: score={score:.4f} up_prob_3d={p3:.4f} up_prob_5d={p5:.4f}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Check prediction scores from backtest snapshots")
    parser.add_argument("--ts-code", type=str, default="002594.SZ", help="Stock code to inspect")
    args = parser.parse_args()
    asyncio.run(check(args.ts_code))
