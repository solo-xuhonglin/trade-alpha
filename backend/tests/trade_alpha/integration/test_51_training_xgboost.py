"""Integration tests for training service — single training, multiple assertions."""

import pytest
import pytest_asyncio
from trade_alpha.models.training import config, trainer
from trade_alpha.test_config import TEST_STOCK


@pytest.mark.integration
@pytest.mark.order(51)
class TestTrainingService:
    """Integration tests for training service — single training, multiple assertions."""

    @pytest_asyncio.fixture(scope="class")
    async def shared_training(self, test_model_config, ensure_test_stock):
        """Create training once for all tests in this class."""
        existing = await trainer.get_training_by_name("test_training")
        if existing:
            await trainer.delete_training(existing.id)

        training = await trainer.create_training(
            config_id=test_model_config.id,
            name="test_training",
            ts_codes=[TEST_STOCK],
            start_date="20230101",
            end_date="20231231",
        )
        yield training

        trainings = await trainer.list_trainings(config_id=test_model_config.id)
        for t in trainings:
            if t.name == "test_training":
                continue
            await trainer.delete_training(t.id)

    @pytest.mark.asyncio
    async def test_training_metrics(self, test_model_config, shared_training):
        """Verify training metrics."""
        training = shared_training
        assert training.model_path is not None
        assert training.model_metrics["sample_count"] >= 20
        assert isinstance(training.feature_fields, list)
        assert len(training.feature_fields) > 0
        assert training.classification_horizons == [3, 5]

    @pytest.mark.asyncio
    async def test_prediction(self, test_model_config, shared_training):
        """Verify prediction results."""
        training = shared_training
        result = await trainer.predict_with_training(training.id, TEST_STOCK)

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
    async def test_list_trainings(self, test_model_config, shared_training):
        """Verify listing trainings."""
        trainings = await trainer.list_trainings()
        assert len(trainings) > 0

        trainings = await trainer.list_trainings(config_id=test_model_config.id)
        assert all(t.config_id == test_model_config.id for t in trainings)

    @pytest.mark.asyncio
    async def test_delete_training(self, test_model_config, shared_training):
        """Verify deleting training."""
        # Create a temporary training for delete test
        training = await trainer.create_training(
            config_id=test_model_config.id,
            name="test_delete_temp",
            ts_codes=[TEST_STOCK],
            start_date="20230101",
            end_date="20231231",
        )

        deleted = await trainer.delete_training(training.id)
        assert deleted is True

        result = await trainer.get_training_by_id(training.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_ensure_default_training(self, test_model_config, shared_training):
        """Ensure default training exists for Layer 6 tests."""
        trainings = await trainer.list_trainings(config_id=test_model_config.id)
        for t in trainings:
            if t.name == "test_training":
                return
