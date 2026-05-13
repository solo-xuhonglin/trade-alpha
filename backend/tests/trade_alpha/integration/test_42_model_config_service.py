"""Integration tests for model config service."""

import pytest
from trade_alpha.predict import config_service
from trade_alpha.predict.config_service import DEFAULT_INDICATOR_FIELDS


@pytest.mark.integration
@pytest.mark.order(42)
class TestModelConfigService:
    """Integration tests for model config service."""

    @pytest.fixture(autouse=True)
    async def setup_teardown(self):
        """Setup and teardown for each test."""
        self.default_config_name = "test_model_config"

        yield

        configs = await config_service.list_configs()
        for c in configs:
            if c.name != self.default_config_name:
                await config_service.delete_config(c.id)

    @pytest.mark.asyncio
    async def test_create_config(self):
        """Test creating config."""
        config = await config_service.create_config(
            name="test_create_temp",
            model_type="xgboost",
            classification_horizons=[3, 5],
            classification_threshold=0.02,
        )

        assert config is not None
        assert config.model_type == "xgboost"
        assert config.classification_horizons == [3, 5]
        assert config.classification_threshold == 0.02

    @pytest.mark.asyncio
    async def test_create_duplicate_config(self):
        """Test creating duplicate config fails."""
        await config_service.create_config(
            name="test_dup_temp",
            model_type="xgboost",
            classification_horizons=[3, 5],
            classification_threshold=0.02,
        )

        with pytest.raises(ValueError, match="already exists"):
            await config_service.create_config(
                name="test_dup_temp",
                model_type="xgboost",
                classification_horizons=[3, 5],
                classification_threshold=0.02,
            )

    @pytest.mark.asyncio
    async def test_list_configs(self):
        """Test listing configs."""
        await config_service.create_config(
            name="test_list_temp",
            model_type="lstm",
            classification_horizons=[5, 10],
            classification_threshold=0.03,
        )

        configs = await config_service.list_configs()
        assert len(configs) > 0

    @pytest.mark.asyncio
    async def test_update_config(self):
        """Test updating config."""
        config = await config_service.create_config(
            name="test_update_temp",
            model_type="xgboost",
            classification_horizons=[3, 5],
            classification_threshold=0.02,
        )

        updated = await config_service.update_config(config.id, classification_horizons=[5, 10])
        assert updated is not None
        assert updated.classification_horizons == [5, 10]

    @pytest.mark.asyncio
    async def test_delete_config(self):
        """Test deleting config."""
        config = await config_service.create_config(
            name="test_delete_temp",
            model_type="lstm",
            classification_horizons=[3, 5],
            classification_threshold=0.02,
        )

        deleted = await config_service.delete_config(config.id)
        assert deleted is True

        result = await config_service.get_config_by_id(config.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_ensure_default_config(self):
        """Ensure default config exists for Layer 5 tests."""
        existing = await config_service.get_config_by_name(self.default_config_name)
        if existing:
            await existing.delete()

        config = await config_service.create_config(
            name=self.default_config_name,
            model_type="xgboost",
            classification_horizons=[3, 5],
            classification_threshold=0.02,
        )
        assert config.feature_fields == DEFAULT_INDICATOR_FIELDS
        assert config.standardize_fields == DEFAULT_INDICATOR_FIELDS
        assert config.winsorize_fields == []
        assert "label_3d" in config.output_fields
        assert "label_5d" in config.output_fields
