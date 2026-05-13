"""Predictor for backtest execution pipeline."""

from typing import Dict, List
import pandas as pd
from beanie import PydanticObjectId
from trade_alpha.predict.training_service import predict_with_training
from trade_alpha.logging import get_logger

logger = get_logger("execution.predictor")


class Predictor:
    """Batch prediction using trained model."""

    def __init__(self, training_id: PydanticObjectId):
        self.training_id = training_id

    async def predict_batch(self, df: pd.DataFrame, ts_codes: List[str]) -> Dict[str, Dict]:
        result = {}
        for ts_code in ts_codes:
            stock_df = df[df["ts_code"] == ts_code]
            if stock_df.empty:
                continue
            try:
                pred = await predict_with_training(self.training_id, ts_code)
                probs = pred.get("probabilities", {})
                up_prob_3d = probs.get("label_3d", [0, 0, 0])[2] if isinstance(probs.get("label_3d"), list) and len(probs["label_3d"]) == 3 else 0
                up_prob_5d = probs.get("label_5d", [0, 0, 0])[2] if isinstance(probs.get("label_5d"), list) and len(probs["label_5d"]) == 3 else 0
                score = up_prob_3d * 0.4 + up_prob_5d * 0.6
                result[ts_code] = {
                    "up_prob_3d": up_prob_3d,
                    "up_prob_5d": up_prob_5d,
                    "score": score,
                    "close": float(stock_df.iloc[-1]["close"]) if "close" in stock_df.columns else 0,
                }
            except Exception as e:
                logger.warning(f"Predict failed for {ts_code}: {e}")
                continue
        return result

    async def predict_single(self, df: pd.DataFrame, ts_code: str) -> Dict:
        stock_df = df[df["ts_code"] == ts_code]
        if stock_df.empty:
            return {"up_prob_3d": 0, "up_prob_5d": 0, "score": 0}
        try:
            pred = await predict_with_training(self.training_id, ts_code)
            probs = pred.get("probabilities", {})
            up_prob_3d = probs.get("label_3d", [0, 0, 0])[2] if isinstance(probs.get("label_3d"), list) and len(probs["label_3d"]) == 3 else 0
            up_prob_5d = probs.get("label_5d", [0, 0, 0])[2] if isinstance(probs.get("label_5d"), list) and len(probs["label_5d"]) == 3 else 0
            score = up_prob_3d * 0.4 + up_prob_5d * 0.6
            return {"up_prob_3d": up_prob_3d, "up_prob_5d": up_prob_5d, "score": score}
        except Exception as e:
            logger.warning(f"Predict single failed for {ts_code}: {e}")
            return {"up_prob_3d": 0, "up_prob_5d": 0, "score": 0}
