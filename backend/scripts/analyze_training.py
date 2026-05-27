"""Analyze latest training record."""
import asyncio
from trade_alpha.dao.mongodb import init_db
from trade_alpha.dao.training import TrainingResult


async def main():
    await init_db()
    latest = await TrainingResult.find_all().sort(-TrainingResult.created_at).first_or_none()
    if not latest:
        print("No training records found")
        return

    d = latest.model_dump()
    print("=== Training Result ===")
    print("ID:", d["id"])
    print("Name:", d["name"])
    print("Start:", d["start_date"], "End:", d["end_date"])
    print("TS codes count:", len(d["ts_codes"]))

    metrics = d.get("model_metrics", {})
    print()
    print("=== Metrics ===")
    print("Sample count:", metrics.get("sample_count"))
    print("Actual epochs:", metrics.get("actual_epochs"))
    print("Early stopped:", metrics.get("early_stopped"))
    print("Best AUC:", metrics.get("best_auc"))

    snap = d.get("model_snapshot", {})
    if snap:
        print()
        print("=== Model Config ===")
        print("Model Type:", snap.get("model_type"))
        print("Label Mode:", snap.get("label_mode"))
        print("Classification Horizons:", snap.get("classification_horizons"))
        ffs = snap.get("feature_fields", [])
        print("Feature Fields (" + str(len(ffs)) + "):", ffs)
        sfs = snap.get("standardize_fields", [])
        print("Standardize Fields (" + str(len(sfs)) + "):", sfs)
        wfs = snap.get("winsorize_fields", [])
        print("Winsorize Fields (" + str(len(wfs)) + "):", wfs)

    analysis = d.get("normalized_data_analysis")
    if analysis:
        stats = analysis.get("statistics", {})
        print()
        print("=== Data Analysis (field count) ===")
        print("Fields with analysis:", len(stats))
        for field, s in list(stats.items())[:10]:
            cnt = s.get("count", "?")
            mean = s.get("mean", "?")
            std = s.get("std", "?")
            print(f"  {field}: count={cnt}, mean={mean}, std={std}")
        if len(stats) > 10:
            print("  ... and", len(stats) - 10, "more fields")
    else:
        print()
        print("No normalized_data_analysis found")


if __name__ == "__main__":
    asyncio.run(main())
