"""Integration tests for training service."""

import pytest
from trade_alpha.predict import config_service, training_service
from trade_alpha.data import fetch_and_store_stock_daily


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

        config = await config_service.get_config_by_name(self.default_config_name)
        if config:
            self.config_id = config.id
        else:
            config = await config_service.create_config(
                name=self.default_config_name,
                model_type="linear",
                params={},
                targets=["close"],
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

        predictions = await training_service.predict_with_training(training.id)
        assert "close" in predictions

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
