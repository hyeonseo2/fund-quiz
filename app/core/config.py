from __future__ import annotations

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App
    app_env: str = Field(default="local")
    log_level: str = Field(default="INFO")

    # --- Storage / infra
    storage_root: str = Field(default="./storage")
    database_url: str = Field(default="sqlite:///./fund_quiz.db")
    redis_url: str = Field(default="redis://localhost:6379/0")
    app_secret: str = Field(default="dev")
    admin_token: str = Field(default="admin-change-me")

    # --- External APIs
    opendart_api_key: str = Field(default="")
    data_go_kr_service_key: str = Field(default="")
    openai_api_key: str = Field(default="")
    gemini_api_key: str = Field(default="")
    auto_ai_generate_count: int = Field(default=1)
    cors_allow_origins: str = Field(default="*")

    # --- LLM / pipeline
    openai_model: str = Field(default="gpt-4.1-mini")
    openai_base_url: str | None = Field(default=None)

    request_timeout_sec: float = Field(default=20.0)
    request_retries: int = Field(default=3)

    # --- Queue / worker
    worker_poll_interval_sec: float = Field(default=2.0)
    max_retries: int = Field(default=3)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def storage_path(self) -> Path:
        path = Path(self.storage_root)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def storage_root_path(self) -> Path:
        return self.storage_path
