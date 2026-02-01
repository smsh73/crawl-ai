"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "crawl-ai"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    secret_key: SecretStr = Field(default=SecretStr("change-me-in-production"))

    # Database
    database_url: str = "postgresql+asyncpg://crawlai:crawlai@localhost:5432/crawlai"
    redis_url: str = "redis://localhost:6379/0"

    # AI API Keys
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None
    perplexity_api_key: SecretStr | None = None

    # AI Model Settings
    default_ai_provider: Literal["openai", "anthropic", "google", "perplexity"] = "openai"
    openai_model: str = "gpt-4-turbo-preview"
    anthropic_model: str = "claude-3-sonnet-20240229"
    google_model: str = "gemini-pro"
    perplexity_model: str = "pplx-70b-online"

    # AI Request Settings
    ai_request_timeout: int = 60
    ai_max_retries: int = 3

    # Slack
    slack_bot_token: SecretStr | None = None
    slack_default_channel: str = "#ai-alerts"

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    email_from: str = "crawl-ai@example.com"

    # Scheduler
    scheduler_timezone: str = "Asia/Seoul"
    crawler_default_timeout: int = 30
    crawler_max_retries: int = 3

    # Rate Limiting
    rate_limit_requests_per_minute: int = 60

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def available_ai_providers(self) -> list[str]:
        """Return list of AI providers with valid API keys."""
        providers = []
        if self.openai_api_key:
            providers.append("openai")
        if self.google_api_key:
            providers.append("google")
        if self.anthropic_api_key:
            providers.append("anthropic")
        if self.perplexity_api_key:
            providers.append("perplexity")
        return providers


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
