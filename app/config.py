from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Project-local .env must win over a global DATABASE_URL (e.g. Postgres).
        env_ignore_empty=True,
    )

    app_name: str = "Team Knowledge Base"
    # Prefer KB_DATABASE_URL to avoid clashing with a machine-wide DATABASE_URL.
    database_url: str = Field(
        default="sqlite:///./data/knowledge.db",
        validation_alias="KB_DATABASE_URL",
    )
    llm_api_key: str = ""
    llm_base_url: str = "https://api.proxyapi.ru/openai/v1"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.1
    llm_timeout_seconds: float = 60.0
    search_top_k: int = 5
    max_title_length: int = 300
    max_text_length: int = 100_000
    max_question_length: int = 2000


@lru_cache
def get_settings() -> Settings:
    return Settings()
