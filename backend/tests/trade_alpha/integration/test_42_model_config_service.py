"""Integration tests for model config service."""

import pytest
from trade_alpha.models.training import config
from trade_alpha.models.training.config import DEFAULT_INDICATOR_FIELDS
from trade_alpha.test_config import TEST_MODEL_CONFIG_NAME


@pytest.mark.integration
@pytest.mark.order(42)
class TestModelConfigService:
    """Integration tests for model config service."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Setup and teardown for each test."""
        self.default_config_name = TEST_MODEL_CONFIG_NAME

        yield

        configs = await config.list_configs()
        for c in configs:
            if c.name != self.default_config_name:
                await config.delete_config(c.id)

    @pytest.mark.asyncio
    async def test_create_config(self):
        """Test creating config."""
        config_obj = await config.create_config(
            name="test_create_temp",
            model_type="xgboost",
            classification_horizons=[3, 5],
            classification_threshold=0.02,
        )

        assert config_obj is not None
        assert config_obj.model_type == "xgboost"
        assert config_obj.classification_horizons == [3, 5]
        assert config_obj.classification_threshold == 0.02

    @pytest.mark.asyncio
    async def test_create_duplicate_config(self):
        """Test creating duplicate config fails."""
        await config.create_config(
            name="test_dup_temp",
            model_type="xgboost",
            classification_horizons=[3, 5],
            classification_threshold=0.02,
        )

        with pytest.raises(ValueError, match="already exists"):
            await config.create_config(
                name="test_dup_temp",
                model_type="xgboost",
                classification_horizons=[3, 5],
                classification_threshold=0.02,
            )

    @pytest.mark.asyncio
    async def test_list_configs(self):
        """Test listing configs."""
        await config.create_config(
            name="test_list_temp",
            model_type="lstm",
            classification_horizons=[5, 10],
            classification_threshold=0.03,
        )

        configs = await config.list_configs()
        assert len(configs) > 0

    @pytest.mark.asyncio
    async def test_update_config(self):
        """Test updating config."""
        config_obj = await config.create_config(
            name="test_update_temp",
            model_type="xgboost",
            classification_horizons=[3, 5],
            classification_threshold=0.02,
        )

        updated = await config.update_config(config_obj.id, classification_horizons=[5, 10])
        assert updated is not None
        assert updated.classification_horizons == [5, 10]

    @pytest.mark.asyncio
    async def test_delete_config(self):
        """Test deleting config."""
        config_obj = await config.create_config(
            name="test_delete_temp",
            model_type="lstm",
            classification_horizons=[3, 5],
            classification_threshold=0.02,
        )

        deleted = await config.delete_config(config_obj.id)
        assert deleted is True

        result = await config.get_config_by_id(config_obj.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_ensure_default_config(self):
        """Ensure default config exists for Layer 5 tests."""
        existing = await config.get_config_by_name(self.default_config_name)
        if existing:
            await existing.delete()

        config_obj = await config.create_config(
            name=self.default_config_name,
            model_type="xgboost",
            classification_horizons=[3, 5],
            classification_threshold=0.02,
        )
        assert config_obj.feature_fields == DEFAULT_INDICATOR_FIELDS
        assert config_obj.standardize_fields == DEFAULT_INDICATOR_FIELDS
        assert config_obj.winsorize_fields == []
        assert config_obj.classification_horizons == [3, 5]
