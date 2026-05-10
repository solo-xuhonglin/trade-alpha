"""Integration tests for model service."""

import pytest
from trade_alpha.predict import model_service
from trade_alpha.data import fetch_and_store_stock_daily


@pytest.mark.integration
@pytest.mark.order(42)
class TestModelService:
    """Integration tests for model service."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.ts_code = "002594.SZ"
        self.start_date = "20230101"
        self.end_date = "20231231"
        self.default_model_name = "test_model"

        fetch_and_store_stock_daily(self.ts_code, self.start_date, self.end_date)

        yield

        models = model_service.list_models(ts_code=self.ts_code)
        for m in models:
            if m["name"] != self.default_model_name:
                model_service.delete_model(str(m["_id"]))

    def test_create_linear_model(self):
        """Test creating linear model."""
        model_id = model_service.create_model(
            name="test_linear_temp",
            model_type="linear",
            ts_code=self.ts_code,
            targets=["close"],
            params={},
            start_date=self.start_date,
            end_date=self.end_date,
        )

        assert model_id is not None

        model = model_service.get_model_by_id(model_id)
        assert model is not None
        assert model["model_type"] == "linear"

    def test_create_xgboost_model(self):
        """Test creating XGBoost model."""
        model_id = model_service.create_model(
            name="test_xgboost_temp",
            model_type="xgboost",
            ts_code=self.ts_code,
            targets=["close"],
            params={"n_estimators": 50, "max_depth": 4},
            start_date=self.start_date,
            end_date=self.end_date,
        )

        assert model_id is not None

        predictions = model_service.predict_with_model(model_id)
        assert "close" in predictions

    def test_list_models(self):
        """Test listing models."""
        model_service.create_model(
            name="test_list_temp",
            model_type="linear",
            ts_code=self.ts_code,
            targets=["close"],
            params={},
            start_date=self.start_date,
            end_date=self.end_date,
        )

        models = model_service.list_models(ts_code=self.ts_code)
        assert len(models) > 0

    def test_delete_model(self):
        """Test deleting model."""
        model_id = model_service.create_model(
            name="test_delete_temp",
            model_type="linear",
            ts_code=self.ts_code,
            targets=["close"],
            params={},
            start_date=self.start_date,
            end_date=self.end_date,
        )

        deleted = model_service.delete_model(model_id)
        assert deleted is True

        model = model_service.get_model_by_id(model_id)
        assert model is None

    def test_ensure_default_model(self):
        """Ensure default model exists for Layer 5 tests."""
        existing = model_service.list_models(ts_code=self.ts_code)
        for m in existing:
            if m["name"] == self.default_model_name:
                return

        model_service.create_model(
            name=self.default_model_name,
            model_type="linear",
            ts_code=self.ts_code,
            targets=["close"],
            params={},
            start_date=self.start_date,
            end_date=self.end_date,
        )
