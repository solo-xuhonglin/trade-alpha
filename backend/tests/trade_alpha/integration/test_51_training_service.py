"""Integration tests for training service."""

import pytest
from trade_alpha.predict import config_service, training_service
from trade_alpha.dao import StockList


@pytest.mark.integration
@pytest.mark.order(51)
class TestTrainingService:
    """Integration tests for training service."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self, test_model_config, test_stock):
        """Setup and teardown for each test."""
        self.config_id = test_model_config.id
        self.default_training_name = "test_training"
        self.start_date = "20230101"
        self.end_date = "20231231"

        yield

        trainings = await training_service.list_trainings(config_id=self.config_id)
        for t in trainings:
            if t.name != self.default_training_name:
                await training_service.delete_training(t.id)

    @pytest.mark.asyncio
    async def test_create_training_single_stock(self, test_stock):
        """Test creating training with single stock."""
        ts_code = test_stock
        
        training = await training_service.create_training(
            config_id=self.config_id,
            name="test_single_temp",
            ts_codes=[ts_code],
            start_date=self.start_date,
            end_date=self.end_date,
        )

        assert training is not None
        assert ts_code in training.ts_codes
        assert training.classification_horizons == [3, 5]
        assert training.model_path is not None
        assert training.metrics["sample_count"] >= 20
        assert isinstance(training.feature_fields, list)
        assert len(training.feature_fields) > 0

    @pytest.mark.asyncio
    async def test_create_training_multi_stocks(self, test_stock):
        """Test creating training with multiple stocks (test stock + active stocks)."""
        # Get active stocks (excluding test stock)
        active_stocks = await StockList.find(
            StockList.sync_status == "active",
            StockList.ts_code != test_stock,
        ).sort(-StockList.total_mv).limit(2).to_list()
        
        # Combine test stock with up to 2 additional active stocks
        ts_codes = [test_stock] + [s.ts_code for s in active_stocks]
        
        training = await training_service.create_training(
            config_id=self.config_id,
            name="test_multi_temp",
            ts_codes=ts_codes,
            start_date=self.start_date,
            end_date=self.end_date,
        )

        assert training is not None
        assert len(training.ts_codes) >= 1

    @pytest.mark.asyncio
    async def test_list_trainings(self, test_stock):
        """Test listing trainings."""
        await training_service.create_training(
            config_id=self.config_id,
            name="test_list_temp",
            ts_codes=[test_stock],
            start_date=self.start_date,
            end_date=self.end_date,
        )

        trainings = await training_service.list_trainings()
        assert len(trainings) > 0

    @pytest.mark.asyncio
    async def test_list_trainings_by_config(self, test_stock):
        """Test listing trainings by config."""
        await training_service.create_training(
            config_id=self.config_id,
            name="test_filter_temp",
            ts_codes=[test_stock],
            start_date=self.start_date,
            end_date=self.end_date,
        )

        trainings = await training_service.list_trainings(config_id=self.config_id)
        assert all(t.config_id == self.config_id for t in trainings)

    @pytest.mark.asyncio
    async def test_delete_training(self, test_stock):
        """Test deleting training."""
        training = await training_service.create_training(
            config_id=self.config_id,
            name="test_delete_temp",
            ts_codes=[test_stock],
            start_date=self.start_date,
            end_date=self.end_date,
        )

        deleted = await training_service.delete_training(training.id)
        assert deleted is True

        result = await training_service.get_training_by_id(training.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_predict(self, test_stock):
        """Test prediction with trained model."""
        training = await training_service.create_training(
            config_id=self.config_id,
            name="test_predict_temp",
            ts_codes=[test_stock],
            start_date=self.start_date,
            end_date=self.end_date,
        )

        result = await training_service.predict_with_training(training.id, test_stock)
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
    async def test_ensure_default_training(self, test_stock):
        """Ensure default training exists for Layer 6 tests."""
        trainings = await training_service.list_trainings(config_id=self.config_id)
        for t in trainings:
            if t.name == self.default_training_name:
                return

        await training_service.create_training(
            config_id=self.config_id,
            name=self.default_training_name,
            ts_codes=[test_stock],
            start_date=self.start_date,
            end_date=self.end_date,
        )
