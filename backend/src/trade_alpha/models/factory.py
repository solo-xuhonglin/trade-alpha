"""Factory for creating Predictor instances."""
from trade_alpha.models.training.trainer import get_training_by_id
from trade_alpha.models.training.config import get_config_by_id


async def create_predictor(training_id, data_loader=None):
    training = await get_training_by_id(training_id)
    config = await get_config_by_id(training.config_id)

    if config.model_type == "xgboost":
        classifier = XGBoostClassifier(config)
        predictor_class = XGBoostPredictor
    elif config.model_type == "lstm":
        classifier = LSTMClassifier(config)
        predictor_class = LSTMPredictor
    else:
        raise ValueError(f"Unknown model type: {config.model_type}")

    classifier.load(training.model_path)
    return predictor_class(config, classifier, data_loader)
