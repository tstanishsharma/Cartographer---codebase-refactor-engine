"""
Cartographer — Application Configuration.

Uses Pydantic Settings for type-safe, validated configuration loaded
from environment variables and/or .env file.

Pattern: call get_settings() everywhere — the result is cached via
@lru_cache so it is effectively a singleton.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration class for all Cartographer services.

    Environment variable names are the UPPER_SNAKE_CASE version of each field.
    Nested models are populated with a __ delimiter (e.g. DATABASE__HOST).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Silently ignore unknown env vars
    )

    # ── Robustness: inline comments ────────────────────────────────────────
    @model_validator(mode="before")
    @classmethod
    def strip_inline_comments(cls, values: dict) -> dict:
        """
        Strip trailing inline comments from environment values.

        python-dotenv strips inline comments when loading ``.env`` files, but
        pydantic-settings does not — and exported environment variables can
        carry the same ``KEY=value  # comment`` form. Replicate the dotenv
        rule (a ``#`` preceded by whitespace starts a comment) so both sources
        behave identically.
        """
        if isinstance(values, dict):
            for key, value in list(values.items()):
                if isinstance(value, str) and " #" in value:
                    values[key] = value.split(" #", 1)[0].rstrip()
        return values

    # ── Application ────────────────────────────────────────────────────────
    app_name: str = "Cartographer"
    app_version: str = "0.1.0"
    app_env: Literal["development", "production", "test"] = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_workers: int = 1
    secret_key: SecretStr = Field(..., min_length=32)

    # ── Database ───────────────────────────────────────────────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "cartographer"
    postgres_user: str = "cartographer"
    postgres_password: SecretStr = Field(default=SecretStr("cartographer_secret"))

    # Override the full DSN directly if preferred
    database_url: str | None = None
    alembic_database_url: str | None = None

    @model_validator(mode="after")
    def build_database_urls(self) -> Settings:
        if self.database_url is None:
            pw = self.postgres_password.get_secret_value()
            self.database_url = (
                f"postgresql+asyncpg://{self.postgres_user}:{pw}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        if self.alembic_database_url is None:
            pw = self.postgres_password.get_secret_value()
            self.alembic_database_url = (
                f"postgresql+psycopg2://{self.postgres_user}:{pw}"
                f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        return self

    # ── Redis ──────────────────────────────────────────────────────────────
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: SecretStr | None = None
    redis_url: str | None = None

    @model_validator(mode="after")
    def build_redis_url(self) -> Settings:
        if self.redis_url is None:
            pw = self.redis_password.get_secret_value() if self.redis_password else None
            auth = f":{pw}@" if pw else ""
            self.redis_url = f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return self

    # ── JWT ────────────────────────────────────────────────────────────────
    jwt_secret_key: SecretStr = Field(..., min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

    # ── GitHub OAuth ───────────────────────────────────────────────────────
    github_oauth_enabled: bool = False
    github_client_id: str | None = None
    github_client_secret: SecretStr | None = None
    github_callback_url: str = "http://localhost:8000/api/v1/auth/github/callback"

    # ── LLM Providers ─────────────────────────────────────────────────────
    llm_provider: Literal["anthropic", "openai", "ollama"] = "anthropic"
    llm_model: str = "claude-sonnet-4-5"

    # Anthropic
    anthropic_api_key: SecretStr | None = None
    anthropic_base_url: str = "https://api.anthropic.com"

    # OpenAI / compatible
    openai_api_key: SecretStr | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_org_id: str | None = None

    # Ollama (local fallback)
    ollama_enabled: bool = False
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "codellama:13b"

    # ── Embedding Providers ───────────────────────────────────────────────
    embedding_provider: Literal["openai", "bge", "nomic"] = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    openai_embedding_base_url: str = "https://api.openai.com/v1"

    # BGE (local HuggingFace)
    bge_enabled: bool = False
    bge_model_name: str = "BAAI/bge-large-en-v1.5"
    bge_device: Literal["cpu", "cuda", "mps"] = "cpu"

    # Nomic (local HuggingFace or cloud)
    nomic_enabled: bool = False
    nomic_model_name: str = "nomic-embed-text-v1.5"
    nomic_api_key: SecretStr | None = None
    nomic_device: Literal["cpu", "cuda", "mps"] = "cpu"

    # ── Sandbox ────────────────────────────────────────────────────────────
    sandbox_enabled: bool = True
    sandbox_image: str = "cartographer-sandbox:latest"
    sandbox_docker_socket: str = "/var/run/docker.sock"
    sandbox_workspace_base: str = "/tmp/cartographer/sandbox"
    sandbox_max_concurrent: int = 5
    sandbox_timeout_seconds: int = 300
    sandbox_memory_limit: str = "2g"
    sandbox_cpu_limit: float = 2.0
    sandbox_windows_wsl2: bool = False  # Windows + Docker Desktop / WSL2 mode

    # ── Ingestion ─────────────────────────────────────────────────────────
    ingestion_chunk_size: int = 1500
    ingestion_chunk_overlap: int = 200
    ingestion_max_file_size_mb: int = 5
    ingestion_supported_extensions: list[str] = Field(
        default=[
            ".py",
            ".ts",
            ".js",
            ".tsx",
            ".jsx",
            ".java",
            ".go",
            ".rs",
            ".cpp",
            ".c",
            ".h",
            ".md",
            ".yaml",
            ".yml",
            ".json",
            ".toml",
        ]
    )

    # ── Retrieval / RAG ───────────────────────────────────────────────────
    retrieval_top_k_vector: int = 20
    retrieval_top_k_keyword: int = 10
    retrieval_top_k_graph: int = 15
    retrieval_top_k_final: int = 10
    retrieval_graph_traversal_depth: int = 3
    retrieval_reranker_enabled: bool = True
    retrieval_context_compression: bool = True

    # ── Observability ─────────────────────────────────────────────────────
    otel_enabled: bool = False
    otel_service_name: str = "cartographer-backend"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"

    prometheus_enabled: bool = True
    prometheus_port: int = 9090

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    # ── CORS ──────────────────────────────────────────────────────────────
    cors_origins: list[str] = Field(default=["http://localhost:3000", "http://localhost:5173"])
    cors_allow_credentials: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Allow comma-separated string from env var."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("ingestion_supported_extensions", mode="before")
    @classmethod
    def parse_extensions(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [ext.strip() for ext in v.split(",")]
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached application settings singleton.

    Use this everywhere instead of instantiating Settings() directly.
    In tests, call get_settings.cache_clear() to reset between tests.
    """
    return Settings()  # type: ignore[call-arg]
