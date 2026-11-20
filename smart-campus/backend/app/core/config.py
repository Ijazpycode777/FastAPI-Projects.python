"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from typing import List
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # Application
    app_name: str = "Smart Campus"
    app_env: str = Field("development", pattern="^(development|staging|production)$")
    app_log_level: str = "INFO"
    frontend_dist_dir: str = "./frontend/dist"
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql+asyncpg://smartcampus:smartcampus@localhost:5432/smartcampus"
    database_url_sync: str = "postgresql+psycopg2://smartcampus:smartcampus@localhost:5432/smartcampus"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_echo: bool = False

    # Sessions / cookies
    session_cookie_name: str = "smartcampus_session"
    session_secret_key: str = "change-me-to-a-long-random-string"
    session_max_age_seconds: int = 28800
    session_cookie_secure: bool = False
    session_cookie_samesite: str = Field("lax", pattern="^(lax|strict|none)$")

    # CSRF
    csrf_cookie_name: str = "smartcampus_csrf"
    csrf_secure: bool = False

    # CORS — stored as a CSV string so plain env values work without JSON.
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Passwords / Argon2id
    password_min_length: int = 10
    password_max_length: int = 128
    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536
    argon2_parallelism: int = 2

    # Login rate limiting (slowapi notation)
    login_rate_limit: str = "5/minute"
    default_rate_limit: str = "120/minute"

    # Account lockout after repeated failed logins.
    account_lockout_threshold: int = 5
    account_lockout_minutes: int = 15

    # Distinct login failure messages ("Incorrect email." vs "Incorrect password.").
    # True by default so users can tell which credential is wrong. NOTE: distinct
    # messages are a user-enumeration oracle (they reveal which emails exist); set
    # to False in hardened production to collapse both to "Invalid email or password."
    login_distinct_error_messages: bool = True

    # Teacher self-attendance
    teacher_late_threshold_minutes: int = 15
    teacher_work_start: str = "08:30"  # HH:MM

    # File storage
    storage_backend: str = Field("local", pattern="^(local|s3)$")
    storage_local_path: str = "./storage/materials"
    max_upload_mb: int = 25
    allowed_upload_extensions: str = "pdf,docx,pptx,png,jpg,jpeg,webp"

    # Seeding
    seed_admin_email: str = "admin@smartcampus.edu"
    seed_admin_password: str = "ChangeMe!2025"
    seed_reset_on_start: bool = False

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def allowed_extensions(self) -> list[str]:
        return [e.strip().lower() for e in self.allowed_upload_extensions.split(",") if e.strip()]

    def allowed_origin_set(self) -> set[str]:
        return {o.rstrip("/") for o in self.allowed_origins}

    def normalize_database_url_for_render(self) -> str:
        """Render exposes a `postgres://` connection string; convert to asyncpg."""
        url = self.database_url
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://") and "+asyncpg" not in url:
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


def to_sync_url(url: str) -> str:
    """Convert any Postgres connection URL to the synchronous psycopg2 form
    used by Alembic migrations.

    Handles every variant Render/the app may supply:
      * ``postgres://``            (Render's raw connection string)
      * ``postgresql+asyncpg://``  (the async app driver)
      * ``postgresql://``          (bare)
      * ``postgresql+psycopg2://`` (already sync — returned as-is)
    Non-Postgres URLs (e.g. ``sqlite://`` for local tests) are returned unchanged.
    """
    if not url:
        return url
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://"):]
    if url.startswith("postgresql+"):
        # postgresql+asyncpg://  ->  postgresql+psycopg2://
        return "postgresql+psycopg2://" + url.split("://", 1)[1]
    return url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
