"""FinSight shared settings — pluggable, free/open-source stack."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    llm_provider: Literal["ollama", "groq", "together", "mock"] = "mock"
    llm_model: str = "llama-3.1-8b"
    ollama_base_url: str = "http://localhost:11434"
    groq_api_key: str = ""
    together_api_key: str = ""

    # Retrieval
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    reranker_model: str = "BAAI/bge-reranker-base"
    lightweight_mode: bool = True
    retrieval_confidence_threshold: float = 0.08
    groundedness_max_retries: int = 1
    bm25_top_k: int = 20
    dense_top_k: int = 20
    rerank_top_k: int = 5

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "finsight_knowledge"
    qdrant_in_memory: bool = True

    # DB
    database_url: str = "postgresql+asyncpg://finsight:finsight@localhost:5432/finsight"
    database_url_sync: str = "sqlite:///./data/finsight.db"
    use_sqlite: bool = True

    # Auth
    jwt_secret: str = "change-me-in-production-use-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    demo_customer_user: str = "customer"
    demo_customer_pass: str = "demo1234"
    demo_staff_user: str = "staff"
    demo_staff_pass: str = "staff1234"

    rate_limit_per_minute: int = 30
    pii_redaction_enabled: bool = True

    # Observability
    langfuse_enabled: bool = False
    langfuse_host: str = "http://localhost:3000"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:8501,http://localhost:8502"

    default_access_role: str = "customer"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
