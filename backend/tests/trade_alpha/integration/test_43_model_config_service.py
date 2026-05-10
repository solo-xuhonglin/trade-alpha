"""Integration tests for model config service."""

import pytest
from trade_alpha.predict import config_service


@pytest.mark.integration
@pytest.mark.order(43)
class TestModelConfigService:
    """Integration tests for model config service."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test."""
        self.default_config_name = "test_model_config"

        yield

        configs = config_service.list_configs()
        for c in configs:
            if c["name"] != self.default_config_name:
                config_service.delete_config(str(c["_id"]))

    def test_create_config(self):
        """Test creating config."""
        config_id = config_service.create_config(
            name="test_create_temp",
            model_type="xgboost",
            params={"n_estimators": 50},
            targets=["close"],
        )

        assert config_id is not None

        config = config_service.get_config_by_id(config_id)
        assert config is not None
        assert config["model_type"] == "xgboost"

    def test_create_duplicate_config(self):
        """Test creating duplicate config fails."""
        config_service.create_config(
            name="test_dup_temp",
            model_type="linear",
            params={},
            targets=["close"],
        )

        with pytest.raises(ValueError, match="already exists"):
            config_service.create_config(
                name="test_dup_temp",
                model_type="linear",
                params={},
                targets=["close"],
            )

    def test_list_configs(self):
        """Test listing configs."""
        config_service.create_config(
            name="test_list_temp",
            model_type="linear",
            params={},
            targets=["close"],
        )

        configs = config_service.list_configs()
        assert len(configs) > 0

    def test_update_config(self):
        """Test updating config."""
        config_id = config_service.create_config(
            name="test_update_temp",
            model_type="linear",
            params={},
            targets=["close"],
        )

        config_service.update_config(config_id, params={"n_estimators": 100})

        config = config_service.get_config_by_id(config_id)
        assert config["params"]["n_estimators"] == 100

    def test_delete_config(self):
        """Test deleting config."""
        config_id = config_service.create_config(
            name="test_delete_temp",
            model_type="linear",
            params={},
            targets=["close"],
        )

        deleted = config_service.delete_config(config_id)
        assert deleted is True

        config = config_service.get_config_by_id(config_id)
        assert config is None

    def test_ensure_default_config(self):
        """Ensure default config exists for Layer 5 tests."""
        existing = config_service.get_config_by_name(self.default_config_name)
        if existing:
            return

        config_service.create_config(
            name=self.default_config_name,
            model_type="linear",
            params={},
            targets=["close"],
        )
