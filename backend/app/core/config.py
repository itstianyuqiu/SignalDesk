from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["local", "development", "staging", "production"] = "local"
    cors_origins: str = Field(
        default="http://localhost:3000",
        description="Comma-separated list of allowed CORS origins (no spaces).",
    )

    database_url: str | None = Field(
        default=None,
        description="Async SQLAlchemy URL, e.g. postgresql+asyncpg://user:pass@host:5432/db",
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
        description="Supabase JWT secret (Settings → API → JWT Secret) for HS256 bearer tokens.",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
