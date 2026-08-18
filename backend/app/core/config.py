"""
Application configuration.

Loads settings from environment variables (and a local .env file, if present)
using pydantic-settings. This is the single source of truth for configuration
across the backend -- no module should read os.environ directly; import
`settings` from here instead.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App ---
    app_name: str = "Floor Plan to 3D Building Intelligence API"
    app_env: str = "development"  # development | production
    debug: bool = True

    # --- Database ---
    database_url: str = "sqlite:///./dev.db"

    # --- CORS ---
    # Comma-separated origins in the environment, parsed into a list here.
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # --- Storage ---
    storage_path: str = "./data/uploads"

    # --- LLM API (placeholders only -- consumed starting Phase 6) ---
    llm_provider: str = "openai"
    llm_api_key: str = ""

    # --- Logging ---
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor so the environment is only parsed once."""
    return Settings()


settings = get_settings()
