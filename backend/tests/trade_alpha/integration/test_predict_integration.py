"""Integration tests for prediction service."""

import pytest
from trade_alpha.predict import config_service, training_service
from trade_alpha.dao import PredictionResult, StockList
from trade_alpha.data import fetch_and_store_stock_daily
from trade_alpha.indicators import calculate_and_store_ma, calculate_and_store_macd, calculate_and_store_custom_indicators


@pytest.mark.integration
@pytest.mark.order(4)
class TestPredictIntegration:
    """Integration tests with real MongoDB."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Setup and teardown for each test."""
        self.ts_code = "002594.SZ"
        self.config_name = "test_integration_config"
        self.start_date = "20230101"
        self.end_date = "20231231"

        await fetch_and_store_stock_daily(self.ts_code, self.start_date, self.end_date)
        await calculate_and_store_ma(self.ts_code)
        await calculate_and_store_macd(self.ts_code)
        await calculate_and_store_custom_indicators(self.ts_code)

        stock = await StockList.find_one(StockList.ts_code == self.ts_code)
        if stock:
            stock.sync_status = "active"
            await stock.save()

        config = await config_service.get_config_by_name(self.config_name)
        if config and config.model_type == "xgboost":
            self.config_id = config.id
        else:
            if config:
                await config_service.delete_config(config.id)
            config = await config_service.create_config(
                name=self.config_name,
                model_type="xgboost",
                feature_fields=["ma_5", "ma_10", "ma_20", "macd", "macd_signal", "macd_hist"],
                classification_horizons=[3, 5],
                classification_threshold=0.02,
            )
            self.config_id = config.id

        self.training = await training_service.create_training(
            config_id=self.config_id,
            name="test_integration_training",
            ts_codes=[self.ts_code],
            start_date=self.start_date,
            end_date=self.end_date,
        )

        yield

        await PredictionResult.find(PredictionResult.ts_code == self.ts_code).delete()

    @pytest.mark.asyncio
    async def test_predict_with_training(self):
        """Test predict_with_training returns classification predictions."""
        result = await training_service.predict_with_training(self.training.id, self.ts_code)

        assert "predictions" in result
        assert "probabilities" in result
        assert "label_3d" in result["predictions"]
        assert "label_5d" in result["predictions"]
        assert result["predictions"]["label_3d"] in [-1, 0, 1]
        assert result["predictions"]["label_5d"] in [-1, 0, 1]
        assert len(result["probabilities"]["label_3d"]) == 3
        assert abs(sum(result["probabilities"]["label_3d"]) - 1.0) < 0.01

    @pytest.mark.asyncio
    async def test_get_prediction_by_id(self):
        """Test get_prediction_by_id returns prediction with training_result_id."""
        await training_service.predict_with_training(self.training.id, self.ts_code)

        pred_records = await PredictionResult.find(
            PredictionResult.training_result_id == self.training.id,
            PredictionResult.ts_code == self.ts_code
        ).to_list()
        assert len(pred_records) > 0

        pred = await training_service.get_prediction_by_id(pred_records[0].id)
        assert pred is not None
        assert pred.training_result_id == self.training.id
        assert pred.ts_code == self.ts_code
        assert "label_3d" in pred.predictions
        assert pred.predictions["label_3d"] in [-1, 0, 1]

    @pytest.mark.asyncio
    async def test_delete_prediction(self):
        """Test delete_prediction removes prediction."""
        await training_service.predict_with_training(self.training.id, self.ts_code)

        pred_records = await PredictionResult.find(
            PredictionResult.training_result_id == self.training.id,
            PredictionResult.ts_code == self.ts_code
        ).to_list()
        assert len(pred_records) > 0

        pred_id = pred_records[0].id
        deleted = await training_service.delete_prediction(pred_id)
        assert deleted is True

        pred = await training_service.get_prediction_by_id(pred_id)
        assert pred is None

    @pytest.mark.asyncio
    async def test_get_prediction_not_found(self):
        """Test get_prediction_by_id returns None for non-existent prediction."""
        from beanie import PydanticObjectId
        fake_id = PydanticObjectId("000000000000000000000000")
        pred = await training_service.get_prediction_by_id(fake_id)
        assert pred is None

    @pytest.mark.asyncio
    async def test_delete_prediction_not_found(self):
        """Test delete_prediction returns False for non-existent prediction."""
        from beanie import PydanticObjectId
        fake_id = PydanticObjectId("000000000000000000000000")
        deleted = await training_service.delete_prediction(fake_id)
        assert deleted is False
