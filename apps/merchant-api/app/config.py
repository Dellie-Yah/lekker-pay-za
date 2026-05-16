"""Application configuration using pydantic-settings."""

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sys import path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=Path(Path.cwd() / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://lekker_pay:lekker_pay_dev@localhost:5432/lekker_pay",
        description="PostgreSQL connection URL",
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # PayFast Configuration
    payfast_merchant_id: str = Field(
        default="10000100",
        description="PayFast merchant ID",
    )
    payfast_merchant_key: str = Field(
        default="46f0cd694581a",
        description="PayFast merchant key",
    )
    payfast_passphrase: str = Field(
        default="",
        description="PayFast passphrase (empty for sandbox without passphrase)",
    )
    payfast_sandbox: bool = Field(
        default=True,
        description="Use PayFast sandbox environment",
    )

    # Application
    webhook_base_url: str = Field(
        default="http://localhost:8000",
        description="Base URL for webhook callbacks (will be replaced by cloudflared URL)",
    )


# Global settings instance
settings = Settings()

# Made with Bob
