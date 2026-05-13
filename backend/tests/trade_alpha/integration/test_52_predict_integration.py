"""Integration tests for prediction service."""

import pytest
from trade_alpha.predict import training_service
from trade_alpha.dao import PredictionResult


@pytest.mark.integration
@pytest.mark.order(52)
class TestPredictIntegration:
    """Integration tests with real MongoDB."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self, test_stock):
        """Setup and teardown for each test."""
        self.ts_code = test_stock
        self.start_date = "20230101"
        self.end_date = "20231231"

        yield

        await PredictionResult.find(PredictionResult.ts_code == self.ts_code).delete()

    @pytest.fixture(scope="module")
    async def training_fixture(self, test_stock, test_model_config):
        """Fixture to create training once for all tests."""
        training = await training_service.create_training(
            config_id=test_model_config.id,
            name="test_predict_integration_training",
            ts_codes=[test_stock],
            start_date=self.start_date,
            end_date=self.end_date,
        )
        return training

    @pytest.mark.asyncio
    async def test_predict_with_training(self, test_stock, test_model_config):
        """Test predict_with_training returns classification predictions."""
        # Create training
        training = await training_service.create_training(
            config_id=test_model_config.id,
            name="test_predict_temp",
            ts_codes=[test_stock],
            start_date=self.start_date,
            end_date=self.end_date,
        )
        
        result = await training_service.predict_with_training(training.id, test_stock)

        assert "predictions" in result
        assert "probabilities" in result
        assert "label_3d" in result["predictions"]
        assert "label_5d" in result["predictions"]
        assert result["predictions"]["label_3d"] in [-1, 0, 1]
        assert result["predictions"]["label_5d"] in [-1, 0, 1]
        assert len(result["probabilities"]["label_3d"]) == 3
        assert abs(sum(result["probabilities"]["label_3d"]) - 1.0) < 0.01

    @pytest.mark.asyncio
    async def test_get_prediction_by_id(self, test_stock, test_model_config):
        """Test get_prediction_by_id returns prediction with training_result_id."""
        training = await training_service.create_training(
            config_id=test_model_config.id,
            name="test_get_prediction_temp",
            ts_codes=[test_stock],
            start_date=self.start_date,
            end_date=self.end_date,
        )
        
        await training_service.predict_with_training(training.id, test_stock)

        pred_records = await PredictionResult.find(
            PredictionResult.training_result_id == training.id,
            PredictionResult.ts_code == test_stock
        ).to_list()
        assert len(pred_records) > 0

        pred = await training_service.get_prediction_by_id(pred_records[0].id)
        assert pred is not None
        assert pred.training_result_id == training.id
        assert pred.ts_code == test_stock
        assert "label_3d" in pred.predictions
        assert pred.predictions["label_3d"] in [-1, 0, 1]

    @pytest.mark.asyncio
    async def test_delete_prediction(self, test_stock, test_model_config):
        """Test delete_prediction removes prediction."""
        training = await training_service.create_training(
            config_id=test_model_config.id,
            name="test_delete_prediction_temp",
            ts_codes=[test_stock],
            start_date=self.start_date,
            end_date=self.end_date,
        )
        
        await training_service.predict_with_training(training.id, test_stock)

        pred_records = await PredictionResult.find(
            PredictionResult.training_result_id == training.id,
            PredictionResult.ts_code == test_stock
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
