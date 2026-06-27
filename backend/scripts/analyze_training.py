"""Analyze trend mode details and compare with other modes."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from dotenv import load_dotenv
load_dotenv()
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from trade_alpha.config import load_config

async def main():
    cfg = load_config()
    c = AsyncIOMotorClient(cfg.mongodb_uri)
    db = c[cfg.mongodb_db]

    # 1. Show all model configs with their label_mode
    print("=== ALL CONFIGS ===")
    configs = await db.model_configs.find().sort("created_at", -1).to_list()
    for cfg_doc in configs:
        name = cfg_doc.get("name", "?")
        mode = cfg_doc.get("label_mode", "?")
        th = f'{cfg_doc.get("classification_threshold_3d")}/{cfg_doc.get("classification_threshold_5d")}'
        print(f"  {name:40s} mode={mode:12s} th={th:10s} id={str(cfg_doc['_id'])[-8:]}")

    # 2. Show training results + their config mapping
    print("\n=== TRAINING RESULTS + CONFIG ===")
    docs = await db["training_results"].find().sort("created_at", -1).limit(8).to_list()
    for d in docs:
        tid = str(d["_id"])[-8:]
        cid = str(d.get("config_id", "?"))[-8:] if d.get("config_id") else "?"
        cfg_doc = await db.model_configs.find_one({"_id": d["config_id"]}) if d.get("config_id") else None
        mode = cfg_doc.get("label_mode", "?") if cfg_doc else "?"
        created = d.get("created_at", "?")
        mm = d.get("model_metrics") or {}
        auc = mm.get("auc", {})
        acc = mm.get("accuracy", {})
        cd = mm.get("class_distribution", {})
        print(f"\n  train={tid} config={cid} mode={mode:12s} created={str(created)[:16]}")
        for h in ["label_3d", "label_5d", "label_10d"]:
            a = auc.get(h, "N/A")
            ac = acc.get(h, "N/A")
            dist = cd.get(h, {})
            print(f"    {h}: AUC={a:.3f} acc={ac:.3f} dist={dist}" if isinstance(a, float) else f"    {h}: {a}")

    # 3. Backtest results by config
    print("\n=== BACKTEST RESULTS ===")
    bts = await db.execution_results.find().sort("created_at", -1).limit(10).to_list()
    for bt in bts:
        name = bt.get("name", "?")
        ret = (bt.get("total_return") or 0) * 100
        sharpe = bt.get("sharpe_ratio") or 0
        trades = len(bt.get("execution_trades") or [])
        config_id = bt.get("config_id")
        cfg_doc = await db.model_configs.find_one({"_id": config_id}) if config_id else None
        mode = cfg_doc.get("label_mode", "?") if cfg_doc else "?"
        print(f"  {name:45s} ret={ret:>6.1f}% sharpe={sharpe:.2f} trades={trades:>4d} mode={mode}")

    c.close()

asyncio.run(main())
