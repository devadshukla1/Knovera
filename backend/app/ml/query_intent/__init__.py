"""Query Intent Classification ML module for Knovera."""

from backend.app.ml.query_intent.taxonomy import (
    TAXONOMY_VERSION,
    IntentCategoryEnum,
    AuxiliaryQueryAttributes,
    IntentCategory,
    TaxonomyRegistry,
    MULTI_INTENT_PRECEDENCE,
    OPERATIONAL_CATEGORIES,
)
from backend.app.ml.query_intent.dataset_validator import (
    VALID_SOURCE_TYPES,
    VALID_ANNOTATION_STATUSES,
    VALID_SPLITS,
    DatasetValidationError,
    DatasetValidationReport,
    QueryIntentDatasetValidator,
)
from backend.app.ml.query_intent.preprocessing import (
    PREPROCESSING_VERSION,
    DEFAULT_MAX_QUERY_LENGTH,
    PreprocessedQuery,
    QueryPreprocessor,
)
from backend.app.ml.query_intent.features import (
    TECHNICAL_TOKEN_PATTERN,
    FeatureExtractionStats,
    FeatureType,
    build_char_vectorizer,
    build_feature_pipeline,
    build_word_vectorizer,
    compute_feature_stats,
)
from backend.app.ml.query_intent.metrics import (
    calculate_calibration_metrics,
    calculate_classification_metrics,
    format_classification_report_table,
    format_comparison_table,
)
from backend.app.ml.query_intent.logistic_model import (
    build_logistic_pipeline,
    train_logistic_regression,
)
from backend.app.ml.query_intent.svm_model import (
    build_svm_pipeline,
    train_linear_svm,
)
from backend.app.ml.query_intent.artifacts import (
    DEFAULT_MODELS_ROOT,
    compute_file_sha256,
    load_model_artifact,
    save_model_artifact,
)
from backend.app.ml.query_intent.predictor import (
    QueryIntentPrediction,
    QueryIntentPredictor,
)
from backend.app.ml.query_intent.service import (
    QueryIntentInferenceError,
    QueryIntentModelUnavailableError,
    QueryIntentService,
    QueryIntentServiceError,
    QueryIntentValidationError,
)
from backend.app.ml.query_intent.router import (
    INTENT_ROUTES,
    ROUTING_CONFIG_VERSION,
    IntentRouter,
    IntentRoutingDecision,
)

__all__ = [
    # Taxonomy (C5.1)
    "TAXONOMY_VERSION",
    "IntentCategoryEnum",
    "AuxiliaryQueryAttributes",
    "IntentCategory",
    "TaxonomyRegistry",
    "MULTI_INTENT_PRECEDENCE",
    "OPERATIONAL_CATEGORIES",
    # Dataset Validation (C5.2)
    "VALID_SOURCE_TYPES",
    "VALID_ANNOTATION_STATUSES",
    "VALID_SPLITS",
    "DatasetValidationError",
    "DatasetValidationReport",
    "QueryIntentDatasetValidator",
    # Preprocessing (C5.3)
    "PREPROCESSING_VERSION",
    "DEFAULT_MAX_QUERY_LENGTH",
    "PreprocessedQuery",
    "QueryPreprocessor",
    # Features (C5.4)
    "TECHNICAL_TOKEN_PATTERN",
    "FeatureExtractionStats",
    "FeatureType",
    "build_char_vectorizer",
    "build_feature_pipeline",
    "build_word_vectorizer",
    "compute_feature_stats",
    # Metrics (C5.5 / C5.6 / C5.7)
    "calculate_calibration_metrics",
    "calculate_classification_metrics",
    "format_classification_report_table",
    "format_comparison_table",
    # Logistic Regression (C5.5)
    "build_logistic_pipeline",
    "train_logistic_regression",
    # SVM Classifier (C5.6)
    "build_svm_pipeline",
    "train_linear_svm",
    # Artifacts
    "DEFAULT_MODELS_ROOT",
    "compute_file_sha256",
    "load_model_artifact",
    "save_model_artifact",
    # Prediction (C5.5 / C5.6)
    "QueryIntentPrediction",
    "QueryIntentPredictor",
    # Service (C5.8)
    "QueryIntentService",
    "QueryIntentServiceError",
    "QueryIntentModelUnavailableError",
    "QueryIntentInferenceError",
    "QueryIntentValidationError",
    # Router (C5.9)
    "IntentRouter",
    "IntentRoutingDecision",
    "INTENT_ROUTES",
    "ROUTING_CONFIG_VERSION",
]
