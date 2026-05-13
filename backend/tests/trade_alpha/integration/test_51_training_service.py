"""Integration tests for training service."""

import pytest
from trade_alpha.predict import config_service, training_service
from trade_alpha.data import fetch_and_store_stock_daily
from trade_alpha.indicators import calculate_and_store_ma, calculate_and_store_macd, calculate_and_store_custom_indicators
from trade_alpha.dao import StockList


@pytest.mark.integration
@pytest.mark.order(51)
class TestTrainingService:
    """Integration tests for training service."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Setup and teardown for each test."""
        self.ts_code = "002594.SZ"
        self.backup_ts_code = "601398.SH"
        self.start_date = "20230101"
        self.end_date = "20231231"
        self.default_config_name = "test_model_config"
        self.default_training_name = "test_training"

        await fetch_and_store_stock_daily(self.ts_code, self.start_date, self.end_date)
        await fetch_and_store_stock_daily(self.backup_ts_code, self.start_date, self.end_date)

        for ts_code in [self.ts_code, self.backup_ts_code]:
            await calculate_and_store_ma(ts_code)
            await calculate_and_store_macd(ts_code)
            await calculate_and_store_custom_indicators(ts_code)
            stock = await StockList.find_one(StockList.ts_code == ts_code)
            if stock:
                stock.sync_status = "active"
                await stock.save()

        config = await config_service.get_config_by_name(self.default_config_name)
        if config and config.model_type == "xgboost":
            self.config_id = config.id
        else:
            if config:
                await config_service.delete_config(config.id)
            config = await config_service.create_config(
                name=self.default_config_name,
                model_type="xgboost",
                classification_horizons=[3, 5],
                classification_threshold=0.02,
            )
            self.config_id = config.id

        yield

        trainings = await training_service.list_trainings(config_id=self.config_id)
        for t in trainings:
            if t.name != self.default_training_name:
                await training_service.delete_training(t.id)

    @pytest.mark.asyncio
    async def test_create_training_single_stock(self):
        """Test creating training with single stock."""
        training = await training_service.create_training(
            config_id=self.config_id,
            name="test_single_temp",
            ts_codes=[self.ts_code],
            start_date=self.start_date,
            end_date=self.end_date,
        )

        assert training is not None
        assert self.ts_code in training.ts_codes
        assert training.classification_horizons == [3, 5]
        assert training.model_path is not None
        assert training.metrics["sample_count"] >= 20
        assert isinstance(training.feature_fields, list)
        assert len(training.feature_fields) > 0

    @pytest.mark.asyncio
    async def test_create_training_multi_stocks(self):
        """Test creating training with multiple stocks."""
        training = await training_service.create_training(
            config_id=self.config_id,
            name="test_multi_temp",
            ts_codes=[self.ts_code, self.backup_ts_code],
            start_date=self.start_date,
            end_date=self.end_date,
        )

        assert training is not None
        assert len(training.ts_codes) == 2

    @pytest.mark.asyncio
    async def test_list_trainings(self):
        """Test listing trainings."""
        await training_service.create_training(
            config_id=self.config_id,
            name="test_list_temp",
            ts_codes=[self.ts_code],
            start_date=self.start_date,
            end_date=self.end_date,
        )

        trainings = await training_service.list_trainings()
        assert len(trainings) > 0

    @pytest.mark.asyncio
    async def test_list_trainings_by_config(self):
        """Test listing trainings by config."""
        await training_service.create_training(
            config_id=self.config_id,
            name="test_filter_temp",
            ts_codes=[self.ts_code],
            start_date=self.start_date,
            end_date=self.end_date,
        )

        trainings = await training_service.list_trainings(config_id=self.config_id)
        assert all(t.config_id == self.config_id for t in trainings)

    @pytest.mark.asyncio
    async def test_delete_training(self):
        """Test deleting training."""
        training = await training_service.create_training(
            config_id=self.config_id,
            name="test_delete_temp",
            ts_codes=[self.ts_code],
            start_date=self.start_date,
            end_date=self.end_date,
        )

        deleted = await training_service.delete_training(training.id)
        assert deleted is True

        result = await training_service.get_training_by_id(training.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_predict(self):
        """Test prediction with trained model."""
        training = await training_service.create_training(
            config_id=self.config_id,
            name="test_predict_temp",
            ts_codes=[self.ts_code],
            start_date=self.start_date,
            end_date=self.end_date,
        )

        result = await training_service.predict_with_training(training.id, self.ts_code)
        assert "predictions" in result
        assert "probabilities" in result
        assert isinstance(result["predictions"], dict)
        assert isinstance(result["probabilities"], dict)

        assert "label_3d" in result["predictions"]
        assert "label_5d" in result["predictions"]
        assert result["predictions"]["label_3d"] in [-1, 0, 1]
        assert result["predictions"]["label_5d"] in [-1, 0, 1]

        assert "label_3d" in result["probabilities"]
        assert "label_5d" in result["probabilities"]
        assert len(result["probabilities"]["label_3d"]) == 3
        assert len(result["probabilities"]["label_5d"]) == 3

        total_prob_3d = sum(result["probabilities"]["label_3d"])
        total_prob_5d = sum(result["probabilities"]["label_5d"])
        assert abs(total_prob_3d - 1.0) < 0.01
        assert abs(total_prob_5d - 1.0) < 0.01

    @pytest.mark.asyncio
    async def test_ensure_default_training(self):
        """Ensure default training exists for Layer 6 tests."""
        trainings = await training_service.list_trainings(config_id=self.config_id)
        for t in trainings:
            if t.name == self.default_training_name:
                return

        await training_service.create_training(
            config_id=self.config_id,
            name=self.default_training_name,
            ts_codes=[self.ts_code],
            start_date=self.start_date,
            end_date=self.end_date,
        )
