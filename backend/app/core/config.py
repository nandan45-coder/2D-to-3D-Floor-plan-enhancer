"""
Application configuration.

Prompt 38: relative paths (SQLite database, uploads folder, YOLO model, the .env file itself) are resolved against
the backend folder, not the folder the server happens to be started from (P37-19: starting uvicorn from the project
root silently used a new empty database and no YOLO model). DEBUG is off unless set (P37-03).
"""
import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _from_backend(path: str) -> str:
    return path if not path or os.path.isabs(path) else str((BACKEND_DIR / path).resolve())


def _sqlite_from_backend(url: str) -> str:
    """sqlite:///./dev.db -> sqlite:///<backend>/dev.db; absolute paths, :memory: and other databases unchanged."""
    prefix = "sqlite:///"
    if not url.startswith(prefix) or url.startswith(prefix + "/"):
        return url
    path = url[len(prefix):]
    if not path or path.startswith(":memory:") or os.path.isabs(path):
        return url
    return prefix + (BACKEND_DIR / path).resolve().as_posix()


class Settings(BaseSettings):
    app_name: str = "Floor Plan to 3D Building Intelligence API"
    app_env: str = "development"
    debug: bool = False          # Prompt 38: tracebacks are never sent to the browser unless DEBUG=true

    database_url: str = "sqlite:///./dev.db"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    storage_path: str = "./data/uploads"
    # UI-2 accounts: session lifetime and cookie (set SESSION_COOKIE_SECURE=true behind HTTPS in production)
    session_days: int = 30
    session_cookie_name: str = "bi_session"
    session_cookie_secure: bool = False

    # Prompt 38A: email for "Forgot password?" codes. Empty SMTP_HOST = not set up: in development the code is
    # printed in the backend terminal instead; in production the feature answers "not set up on this server".
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""            # the sender address; empty = SMTP_USERNAME
    smtp_security: str = "starttls"   # starttls (port 587), ssl (port 465) or none
    smtp_timeout_s: float = 20.0

    # LLM assistant (Prompt 22, docs/LLM_ASSISTANT_DESIGN.md): "openai", "gemini" or "offline".
    # Without an API key or model the assistant runs in offline (simple) mode -- no key needed.
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model: str = ""          # a current tool-calling model of the provider, e.g. from its docs
    llm_base_url: str = ""       # optional override (proxy / compatible endpoint); empty = provider default
    llm_timeout_s: float = 20.0
    llm_max_tool_rounds: int = 6   # multi-step questions (surfaces -> calculate -> ...) need a few rounds

    log_level: str = "INFO"
    # Prompt 39: the interactive API pages (/docs, /redoc, /openapi.json) -- on in development, off in production
    # unless ENABLE_API_DOCS=true
    enable_api_docs: Optional[bool] = None

    # --- Detection: Tier 1 pretrained object detector (YOLO) -------------
    # Resolves the "Tier 1 not available" open question from Prompt 5/6.
    # Path is relative to the backend/ working directory by default,
    # pointing at the top-level models/detection/ folder per PDF 1's
    # architecture. If the file is missing or yolo_enabled is False, the
    # pipeline falls back to classical CV automatically.
    yolo_model_path: str = "../models/detection/best.pt"
    # Prompt 38: full path to tesseract(.exe); empty = the one on PATH, else C:\Program Files\Tesseract-OCR
    tesseract_cmd: str = ""
    yolo_confidence_threshold: float = 0.25
    yolo_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"), env_file_encoding="utf-8", case_sensitive=False, extra="ignore",
    )

    @field_validator("enable_api_docs", mode="before")
    @classmethod
    def _empty_means_default(cls, value):
        return None if isinstance(value, str) and not value.strip() else value   # "ENABLE_API_DOCS=" in .env

    @model_validator(mode="after")
    def _resolve_relative_paths(self) -> "Settings":
        self.database_url = _sqlite_from_backend(self.database_url)
        self.storage_path = _from_backend(self.storage_path)
        self.yolo_model_path = _from_backend(self.yolo_model_path)
        if self.is_production:
            self.debug = False      # Prompt 39: never send tracebacks to the browser in production, whatever .env says
        return self

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def email_configured(self) -> bool:
        return bool(self.smtp_host.strip())

    @property
    def api_docs_enabled(self) -> bool:
        return (not self.is_production) if self.enable_api_docs is None else self.enable_api_docs

    def production_warnings(self) -> List[str]:
        """Prompt 39: settings that are fine on a laptop but wrong for a deployed site (logged at startup)."""
        if not self.is_production:
            return []
        out = []
        if not self.session_cookie_secure:
            out.append("SESSION_COOKIE_SECURE is false: set it to true once the site is served over HTTPS.")
        if not self.cors_origins_list:
            out.append("CORS_ORIGINS is empty: set it to the address of the website.")
        elif any("localhost" in o or "127.0.0.1" in o for o in self.cors_origins_list):
            out.append("CORS_ORIGINS contains localhost: set it to the real address of the website.")
        if not self.email_configured:
            out.append("SMTP_HOST is empty: 'Forgot password?' answers that email is not set up.")
        if self.llm_provider.lower() != "offline" and not self.llm_api_key:
            out.append("LLM_API_KEY is empty: the assistant runs in simple (offline) mode.")
        return out


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
