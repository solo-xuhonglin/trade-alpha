"""Integration tests for prediction service — shares training from test_51."""

import pytest
import pytest_asyncio
from trade_alpha.predict import training_service
from trade_alpha.dao import PredictionResult
from trade_alpha.test_config import TEST_STOCK


@pytest.mark.integration
@pytest.mark.order(52)
class TestPredictIntegration:
    """Integration tests for prediction — uses training created by test_51."""

    @pytest_asyncio.fixture(autouse=True)
    async def setup_teardown(self):
        """Setup and teardown for each test."""
        self.ts_code = TEST_STOCK
        self.training = await self._find_training()

        yield

        await PredictionResult.find(PredictionResult.ts_code == self.ts_code).delete()

    async def _find_training(self):
        """Find the training created by test_51."""
        trainings = await training_service.list_trainings()
        for t in trainings:
            if t.name == "test_training":
                return t
        pytest.skip("No test_training found — test_51 must run before test_52")
        return None

    @pytest.mark.asyncio
    async def test_predict_with_training(self):
        """Test predict_with_training returns classification predictions."""
        if not self.training:
            pytest.skip("No training found")

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
        if not self.training:
            pytest.skip("No training found")

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
        if not self.training:
            pytest.skip("No training found")

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
