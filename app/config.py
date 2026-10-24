from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "IdeaDock"
    api_prefix: str = "/api"
    app_host: str = "127.0.0.1"
    app_port: int = Field(default=8017, ge=1, le=65535)
    database_url: str = "sqlite:///./storage/ideadock.db"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:8017", "http://127.0.0.1:8017"]
    upload_dir: str = "storage/uploads"
    max_upload_bytes: int = 10 * 1024 * 1024
    stale_after_days: int = 14
    auto_create_epics: bool = True
    auto_create_entities: bool = True
    auto_create_tags: bool = True
    auto_bootstrap_db: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            if value.startswith("["):
                return json.loads(value)
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
