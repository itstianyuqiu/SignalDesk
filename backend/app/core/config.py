from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load `backend/.env` regardless of process cwd (e.g. `uvicorn` started from repo root).
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_ENV_PATH = _BACKEND_ROOT / ".env"
# Populate os.environ before Settings() is first constructed (covers edge cases vs env_file alone).
load_dotenv(_ENV_PATH, encoding="utf-8")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["local", "development", "staging", "production"] = "local"
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        description="Comma-separated list of allowed CORS origins (no spaces).",
    )

    database_url: str | None = Field(
        default=None,
        description="Async SQLAlchemy URL, e.g. postgresql+asyncpg://user:pass@host:5432/db",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def _strip_database_url(cls, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value  # type: ignore[return-value]

    asyncpg_statement_cache_size: int | None = Field(
        default=None,
        ge=0,
        description=(
            "asyncpg prepared-statement cache size. Use 0 with PgBouncer transaction pooling "
            "(e.g. Supabase pooler :6543). If unset, the API infers from DATABASE_URL."
        ),
    )

    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key for embeddings (Phase 2 RAG).",
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model id.",
    )
    embedding_dimensions: int = Field(
        default=1536,
        ge=256,
        le=3072,
        description="Must match DB vector column and model output.",
    )
    chunk_size: int = Field(default=1200, ge=200, le=8000)
    chunk_overlap: int = Field(default=200, ge=0, le=2000)

    supabase_jwt_secret: str | None = Field(
        default=None,
        description="Legacy shared secret for HS256 Supabase access tokens (older projects).",
    )

    copilot_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model id for Responses API (copilot).",
    )
    copilot_retrieval_top_k: int = Field(default=8, ge=1, le=32)
    copilot_min_evidence_score: float = Field(
        default=0.22,
        ge=0.0,
        le=1.0,
        description="Below this max retrieval score, mark evidence as weak.",
    )
    copilot_max_history_messages: int = Field(default=12, ge=0, le=50)

    langsmith_tracing: bool = Field(
        default=False,
        description="When true, emit LangSmith runs for retrieval, tools, model, and synthesis.",
    )
    langsmith_api_key: str | None = Field(
        default=None,
        description="LangSmith API key (optional when tracing is off).",
    )
    langsmith_project: str = Field(
        default="signal-desk",
        description="LangSmith project name for grouped traces.",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
