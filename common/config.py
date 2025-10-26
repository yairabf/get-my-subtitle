"""Configuration management for the subtitle management system."""

import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    redis_job_ttl_completed: int = Field(
        default=604800, env="REDIS_JOB_TTL_COMPLETED"
    )  # 7 days
    redis_job_ttl_failed: int = Field(
        default=259200, env="REDIS_JOB_TTL_FAILED"
    )  # 3 days
    redis_job_ttl_active: int = Field(
        default=0, env="REDIS_JOB_TTL_ACTIVE"
    )  # No expiration

    # RabbitMQ Configuration
    rabbitmq_url: str = Field(
        default="amqp://admin:password@localhost:5672/", env="RABBITMQ_URL"
    )

    # API Configuration
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # Subtitle Sources
    opensubtitles_username: Optional[str] = Field(
        default=None, env="OPENSUBTITLES_USERNAME"
    )
    opensubtitles_password: Optional[str] = Field(
        default=None, env="OPENSUBTITLES_PASSWORD"
    )
    opensubtitles_api_key: Optional[str] = Field(
        default=None, env="OPENSUBTITLES_API_KEY"
    )

    # Translation Service (OpenAI GPT-5-nano)
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5-nano", env="OPENAI_MODEL")
    openai_max_tokens: int = Field(default=4096, env="OPENAI_MAX_TOKENS")
    openai_temperature: float = Field(
        default=0.3, env="OPENAI_TEMPERATURE"
    )  # Lower for consistent translations

    # File Storage
    subtitle_storage_path: str = Field(
        default="./storage/subtitles", env="SUBTITLE_STORAGE_PATH"
    )

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
