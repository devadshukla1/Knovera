"""Application configuration management via Pydantic Settings.

Loads environment variables from root .env or environment with safe defaults,
masks credentials, and computes database connection URIs.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional
from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

# Project root directory (3 levels above this file: core -> app -> backend -> root)
ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_FILE_PATH = ROOT_DIR / ".env"


class Settings(BaseSettings):
    """Global configuration settings for Knovera."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # 1. Application & Server Settings
    APP_ENV: str = "development"
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # 2. Frontend CORS Configuration
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # 3. PostgreSQL Database Settings
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "knovera"
    POSTGRES_USER: str = "knovera_app"
    POSTGRES_PASSWORD: SecretStr = SecretStr("change_me_locally")
    DATABASE_URL: Optional[str] = Field(default=None, repr=False)
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE_SECONDS: int = 1800
    DB_POOL_TIMEOUT_SECONDS: int = 30

    # 4. ChromaDB Vector Store Settings (Phase 3 C3.2)
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001
    CHROMA_SSL: bool = False
    CHROMA_TENANT: str = "default_tenant"
    CHROMA_DATABASE: str = "default_database"
    CHROMA_COLLECTION_PREFIX: str = "knovera_chunks"
    CHROMA_DISTANCE_METRIC: str = "cosine"
    CHROMA_INSERT_BATCH_SIZE: int = 100
    CHROMA_QUERY_TIMEOUT_SECONDS: float = 30.0
    CHROMA_RETRY_MAX_ATTEMPTS: int = 3

    # 5. Local Storage Adapter Settings (Phase 2 Ingestion)
    STORAGE_BACKEND: str = "local"
    STORAGE_LOCAL_PATH: str = "./storage"
    STORAGE_ROOT: str = "./storage/documents"
    MAX_UPLOAD_MB: int = 50
    MAX_UPLOAD_SIZE_BYTES: int = 26214400  # 25 MB default limit
    MAX_PDF_PAGES: int = 500
    MAX_EXTRACTED_TEXT_CHARS: int = 20_000_000
    MAX_PPTX_SLIDES: int = 500
    MAX_DOCX_PARAGRAPHS: int = 10000

    # Ingestion Pipeline & Retry Configuration (Phase 2 C2.6–C2.8)
    PIPELINE_VERSION: str = "v1.0"
    ENABLE_BOILERPLATE_REMOVAL: bool = True
    INGESTION_MAX_ATTEMPTS: int = 3
    INGESTION_RETRY_BASE_SECONDS: int = 10
    INGESTION_RETRY_MAX_SECONDS: int = 300
    INGESTION_LEASE_SECONDS: int = 300  # Worker lock timeout

    # 6. Authentication & Security (Phase 1)
    AUTH_ACCESS_TOKEN_MINUTES: int = 15
    AUTH_REFRESH_TOKEN_DAYS: int = 30
    AUTH_SECRET_KEY: SecretStr = Field(
        default=SecretStr("replace_with_random_secret_in_production"),
        repr=False,
    )

    # 7. Embedding & RAG Configuration (Phase 3 C3.1–C3.3)
    EMBEDDING_PROVIDER: str = "sentence_transformers"
    EMBEDDING_MODEL_ID: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_MODEL_REVISION: str = "main"
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_NORMALIZE: bool = True
    EMBEDDING_MAX_SEQUENCE_LENGTH: int = 256
    EMBEDDING_QUERY_MAX_LENGTH: int = 256
    EMBEDDING_CACHE_DIR: str = "./storage/model_cache"

    SEMANTIC_RETRIEVAL_TOP_K: int = 10
    SEMANTIC_RETRIEVAL_MAX_TOP_K: int = 50
    SEMANTIC_RETRIEVAL_MIN_SCORE: float = 0.0
    SEMANTIC_RETRIEVAL_TIMEOUT_SECONDS: float = 30.0
    SEMANTIC_RETRIEVAL_DISTANCE_METRIC: str = "cosine"

    # 8. Hybrid Retrieval, BM25 & RRF Configuration (Phase 4 C4.1–C4.3)
    RETRIEVAL_MODE: str = "hybrid"  # "hybrid", "semantic", "bm25"
    DENSE_RETRIEVAL_TOP_K: int = 20
    BM25_RETRIEVAL_TOP_K: int = 20
    BM25_K1: float = 1.5
    BM25_B: float = 0.75
    BM25_INDEX_CACHE_MAX_WORKSPACES: int = 50
    HYBRID_RETRIEVAL_TOP_K: int = 10
    RRF_K: int = 60

    # 8b. Cross-Encoder & Reranking Configuration (Phase 4 C4.4–C4.5)
    RERANKER_ENABLED: bool = True
    CROSS_ENCODER_MODEL_ID: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    CROSS_ENCODER_DEVICE: str = "cpu"  # "cpu", "cuda", "auto"
    CROSS_ENCODER_MAX_LENGTH: int = 512
    CROSS_ENCODER_BATCH_SIZE: int = 16
    RERANKER_CANDIDATE_K: int = 50
    RERANKER_FINAL_K: int = 10
    RERANKER_FAILURE_POLICY: str = "error"  # "error", "rrf_only"

    # 8c. Retrieval Evaluation & Optimization Configuration (Phase 4 C4.7–C4.8)
    RETRIEVAL_EVAL_RELEVANCE_THRESHOLD: int = 2
    RETRIEVAL_EVAL_K_VALUES: str = "5,10,20,50"
    RETRIEVAL_OPTIMIZATION_MAX_CONFIGURATIONS: int = 20
    RETRIEVAL_OPTIMIZATION_RANDOM_SEED: int = 42
    RETRIEVAL_MAX_ALLOWED_RECALL_REGRESSION: float = 0.05
    RETRIEVAL_MAX_ALLOWED_NDCG_REGRESSION: float = 0.05
    RETRIEVAL_MAX_P95_LATENCY_MS: float = 500.0

    # 10. Query Intent Classification Configuration (Phase 5 C5.1–C5.6)
    QUERY_INTENT_TAXONOMY_VERSION: str = "1.0.0"
    QUERY_INTENT_PREPROCESSING_VERSION: str = "1.0.0"
    QUERY_INTENT_WORD_NGRAM_MIN: int = 1
    QUERY_INTENT_WORD_NGRAM_MAX: int = 2
    QUERY_INTENT_CHAR_NGRAM_MIN: int = 3
    QUERY_INTENT_CHAR_NGRAM_MAX: int = 5
    QUERY_INTENT_WORD_MAX_FEATURES: int = 50000
    QUERY_INTENT_CHAR_MAX_FEATURES: int = 100000
    QUERY_INTENT_WORD_FEATURE_WEIGHT: float = 1.0
    QUERY_INTENT_CHAR_FEATURE_WEIGHT: float = 1.0
    QUERY_INTENT_RANDOM_STATE: int = 42
    QUERY_INTENT_MAX_CV_FOLDS: int = 5
    QUERY_INTENT_LOGISTIC_C: float = 1.0
    QUERY_INTENT_LOGISTIC_MAX_ITER: int = 2000
    QUERY_INTENT_SVM_C: float = 1.0
    QUERY_INTENT_SVM_MAX_ITER: int = 5000

    # 10b. Query Intent Service & Routing Configuration (Phase 5 C5.7–C5.9)
    QUERY_INTENT_MODEL_DIR: str = "models/query_intent/selected_model"
    QUERY_INTENT_ROUTING_ENABLED: bool = True
    QUERY_INTENT_ROUTING_CONFIG_VERSION: str = "1.0.0"
    QUERY_INTENT_CONFIDENCE_THRESHOLD: float = 0.30
    QUERY_INTENT_LOW_CONFIDENCE_POLICY: str = "default_rag"  # "default_rag", "clarification"
    QUERY_INTENT_MODEL_FAILURE_POLICY: str = "default_rag"  # "default_rag", "controlled_error"
    QUERY_INTENT_DEFAULT_ROUTE: str = "knowledge_retrieval"
    QUERY_INTENT_MAX_QUERY_LENGTH: int = 2000

    # 11. Topic Discovery & Clustering Configuration (Phase 6 C6.1–C6.6)
    TOPIC_MIN_CLUSTERS: int = 2
    TOPIC_MAX_CLUSTERS: int = 10
    TOPIC_K_CANDIDATE_VALUES: str = "2,3,4,5,6,7,8,10"
    TOPIC_SELECTION_PRIMARY_METRIC: str = "silhouette_cosine"
    TOPIC_SILHOUETTE_METRIC_SAMPLE_SIZE: int = 2000
    TOPIC_SILHOUETTE_RANDOM_STATE: int = 42
    TOPIC_STABILITY_RUNS: int = 3
    TOPIC_STABILITY_RANDOM_SEEDS: str = "42,43,44"
    TOPIC_LABEL_KEYWORD_COUNT: int = 10
    TOPIC_REPRESENTATIVE_CHUNK_COUNT: int = 5
    TOPIC_ENABLE_LLM_LABELING: bool = False
    TOPIC_MODELS_DIR: str = "models/topic_clustering"
    TOPIC_DATASETS_DIR: str = "data/topic_clustering"

    # 9. LLM Provider & Generation Configuration (Phase 3 C3.4–C3.6)
    LLM_PROVIDER: str = "groq"
    LLM_MODEL: str = "qwen/qwen3.8-27b"
    LLM_TEMPERATURE: float = 0.2
    LLM_MAX_OUTPUT_TOKENS: int = 1500
    LLM_TIMEOUT_SECONDS: float = 60.0
    LLM_RETRY_MAX_ATTEMPTS: int = 3
    LLM_DEFAULT_CONTEXT_TOKENS: int = 8192
    LLM_DEFAULT_RESERVED_OUTPUT_TOKENS: int = 1500

    # Provider Specific Configurations
    GEMINI_API_KEY: Optional[SecretStr] = Field(default=None, repr=False)
    GEMINI_MODEL: str = "gemini-2.0-flash"

    GROQ_API_KEY: Optional[SecretStr] = Field(default=None, repr=False)
    GROQ_MODEL: str = "qwen/qwen3.8-27b"

    OPENAI_COMPATIBLE_API_KEY: Optional[SecretStr] = Field(default=None, repr=False)
    OPENAI_COMPATIBLE_BASE_URL: Optional[str] = None
    OPENAI_COMPATIBLE_MODEL: Optional[str] = None

    # Context Construction & Token Budgeting (Phase 3 C3.5)
    CONTEXT_MAX_CHUNKS: int = 8
    CONTEXT_MAX_CHUNKS_PER_DOCUMENT: int = 4
    CONTEXT_SAFETY_MARGIN_TOKENS: int = 250

    # Prompt Engineering (Phase 3 C3.6)
    PROMPT_DEFAULT_VERSION: str = "general-qa-v1"

    # Future Model Placeholders (Deferred to Subsequent Phases)
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    NLI_MODEL: str = "cross-encoder/nli-deberta-v3-base"

    @computed_field
    @property
    def resolved_storage_root(self) -> Path:
        """Returns the absolute Path to STORAGE_ROOT resolved against ROOT_DIR."""
        path = Path(self.STORAGE_ROOT)
        if path.is_absolute():
            return path
        return (ROOT_DIR / path).resolve()

    @computed_field(repr=False)
    @property
    def sqlalchemy_database_uri(self) -> str:
        """Assembles or normalizes the SQLAlchemy connection URI with psycopg driver."""
        if self.DATABASE_URL:
            uri = self.DATABASE_URL
            if uri.startswith("postgres://"):
                return uri.replace("postgres://", "postgresql+psycopg://", 1)
            if uri.startswith("postgresql://") and not uri.startswith("postgresql+"):
                return uri.replace("postgresql://", "postgresql+psycopg://", 1)
            return uri
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD.get_secret_value()}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field
    @property
    def safe_database_uri(self) -> str:
        """Returns database URI with sensitive passwords masked."""
        raw_uri = self.sqlalchemy_database_uri
        try:
            return make_url(raw_uri).render_as_string(hide_password=True)
        except Exception:
            return f"postgresql+psycopg://{self.POSTGRES_USER}:***@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


@lru_cache
def get_settings() -> Settings:
    """Returns cached application settings instance."""
    return Settings()


settings = get_settings()
