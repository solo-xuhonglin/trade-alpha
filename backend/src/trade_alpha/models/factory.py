"""Factory for creating classifier and predictor instances."""
from trade_alpha.models.lstm.classifier import LSTMClassifier
from trade_alpha.models.lstm.predictor import LSTMPredictor
from trade_alpha.models.xgboost.classifier import XGBoostClassifier
from trade_alpha.models.xgboost.predictor import XGBoostPredictor


def create_classifier(config, model_path=None):
    if config.model_type == "xgboost":
        classifier = XGBoostClassifier(config)
    elif config.model_type == "lstm":
        classifier = LSTMClassifier(config)
    else:
        raise ValueError(f"Unknown model type: {config.model_type}")
    if model_path:
        classifier.load(model_path)
    return classifier


def create_predictor(config, classifier, data_loader=None):
    if config.model_type == "xgboost":
        return XGBoostPredictor(config, classifier, data_loader)
    elif config.model_type == "lstm":
        return LSTMPredictor(config, classifier, data_loader)
    else:
        raise ValueError(f"Unknown model type: {config.model_type}")
