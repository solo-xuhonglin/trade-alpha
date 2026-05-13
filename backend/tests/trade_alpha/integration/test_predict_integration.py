"""Integration tests for prediction API endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from trade_alpha.predict import config_service, training_service
from trade_alpha.dao import PredictionResult, StockList
from trade_alpha.data import fetch_and_store_stock_daily
from trade_alpha.indicators import calculate_and_store_ma, calculate_and_store_macd, calculate_and_store_custom_indicators
from trade_alpha.api.main import app


@pytest.mark.integration
@pytest.mark.order(4)
class TestPredictIntegration:
    """Integration tests with real MongoDB and API endpoints."""

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
            name="test_api_training",
            ts_codes=[self.ts_code],
            start_date=self.start_date,
            end_date=self.end_date,
        )

        yield

        await PredictionResult.find(PredictionResult.ts_code == self.ts_code).delete()

    @pytest.mark.asyncio
    async def test_predict_via_api(self):
        """Test POST /api/trainings/{id}/predict via API."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/trainings/{self.training.id}/predict",
                json={"ts_code": self.ts_code}
            )
        assert response.status_code == 200
        data = response.json()
        assert "predictions" in data
        assert "probabilities" in data
        assert "label_3d" in data["predictions"]
        assert "label_5d" in data["predictions"]
        assert data["predictions"]["label_3d"] in [-1, 0, 1]
        assert data["predictions"]["label_5d"] in [-1, 0, 1]

    @pytest.mark.asyncio
    async def test_get_prediction_by_id(self):
        """Test GET /api/predict/{prediction_id} returns prediction with training_result_id."""
        result = await training_service.predict_with_training(self.training.id, self.ts_code)

        pred_records = await PredictionResult.find(
            PredictionResult.training_result_id == self.training.id,
            PredictionResult.ts_code == self.ts_code
        ).to_list()
        assert len(pred_records) > 0

        pred_id = str(pred_records[0].id)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/predict/{pred_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["training_result_id"] == str(self.training.id)
        assert data["ts_code"] == self.ts_code
        assert "predictions" in data
        assert "label_3d" in data["predictions"]
        assert data["predictions"]["label_3d"] in [-1, 0, 1]

    @pytest.mark.asyncio
    async def test_delete_prediction(self):
        """Test DELETE /api/predict/{prediction_id} works."""
        result = await training_service.predict_with_training(self.training.id, self.ts_code)

        pred_records = await PredictionResult.find(
            PredictionResult.training_result_id == self.training.id,
            PredictionResult.ts_code == self.ts_code
        ).to_list()
        assert len(pred_records) > 0

        pred_id = str(pred_records[0].id)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            delete_response = await client.delete(f"/api/predict/{pred_id}")
            assert delete_response.status_code == 200
            assert delete_response.json()["deleted"] is True

            get_response = await client.get(f"/api/predict/{pred_id}")
            assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_prediction_not_found(self):
        """Test GET /api/predict/{id} returns 404 for non-existent prediction."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/predict/000000000000000000000000")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_prediction_not_found(self):
        """Test DELETE /api/predict/{id} returns 404 for non-existent prediction."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/predict/000000000000000000000000")

        assert response.status_code == 404
