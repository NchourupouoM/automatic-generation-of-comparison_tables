from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    # Infrastructure
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM Config
    LLM_PROVIDER: str = "openai"  # openai, anthropic, ollama, google
    LLM_MODEL_NAME: str = "gpt-4o"

    # API Keys & URLs
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # PostgreSQL Configuration
    DATABASE_URL: str = Field(
        ..., 
        validation_alias="DATABASE_URL",
        description="SQLAlchemy database connection string. e.g., postgresql://user:pass@host:5432/db"
    )

    # Validation de sécurité pour imposer le protocole postgresql
    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith("postgresql://") and not v.startswith("postgresql+psycopg2://"):
            raise ValueError("DATABASE_URL must be a valid PostgreSQL connection string starting with 'postgresql://'")
        return v

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

settings = Settings()