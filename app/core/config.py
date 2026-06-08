from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()