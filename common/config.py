"""Configuration management for the subtitle management system."""

import os
from typing import List, Optional, Union

from pydantic import Field, field_validator
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

    # Subtitle Sources - OpenSubtitles (XML-RPC)
    opensubtitles_user_agent: str = Field(
        default="get-my-subtitle v1.0", env="OPENSUBTITLES_USER_AGENT"
    )
    opensubtitles_username: Optional[str] = Field(
        default=None, env="OPENSUBTITLES_USERNAME"
    )
    opensubtitles_password: Optional[str] = Field(
        default=None, env="OPENSUBTITLES_PASSWORD"
    )
    opensubtitles_api_key: Optional[str] = Field(
        default=None, env="OPENSUBTITLES_API_KEY"
    )  # Legacy - not used, kept for backward compatibility
    opensubtitles_max_retries: int = Field(default=3, env="OPENSUBTITLES_MAX_RETRIES")
    opensubtitles_retry_delay: int = Field(default=1, env="OPENSUBTITLES_RETRY_DELAY")
    opensubtitles_retry_max_delay: int = Field(
        default=60, env="OPENSUBTITLES_RETRY_MAX_DELAY"
    )  # Maximum backoff delay in seconds
    opensubtitles_retry_exponential_base: int = Field(
        default=2, env="OPENSUBTITLES_RETRY_EXPONENTIAL_BASE"
    )  # Exponential base for backoff calculation

    # Translation Service (OpenAI GPT-5-nano)
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5-nano", env="OPENAI_MODEL")
    openai_max_tokens: int = Field(default=4096, env="OPENAI_MAX_TOKENS")
    openai_temperature: float = Field(
        default=0.3, env="OPENAI_TEMPERATURE"
    )  # Lower for consistent translations

    # Translation Token Limits
    translation_max_tokens_per_chunk: int = Field(
        default=8000, env="TRANSLATION_MAX_TOKENS_PER_CHUNK"
    )  # Maximum tokens per translation chunk
    translation_token_safety_margin: float = Field(
        default=0.8, env="TRANSLATION_TOKEN_SAFETY_MARGIN"
    )  # Safety margin (0.8 = 80% of limit)

    # OpenAI Retry Configuration
    openai_max_retries: int = Field(
        default=3, env="OPENAI_MAX_RETRIES"
    )  # Maximum number of retry attempts after initial try
    openai_retry_initial_delay: float = Field(
        default=2.0, env="OPENAI_RETRY_INITIAL_DELAY"
    )  # Initial delay in seconds before first retry
    openai_retry_max_delay: float = Field(
        default=60.0, env="OPENAI_RETRY_MAX_DELAY"
    )  # Maximum delay in seconds (backoff cap)
    openai_retry_exponential_base: int = Field(
        default=2, env="OPENAI_RETRY_EXPONENTIAL_BASE"
    )  # Exponential base for backoff (2 = double each time)

    # File Storage
    subtitle_storage_path: str = Field(
        default="./storage/subtitles", env="SUBTITLE_STORAGE_PATH"
    )

    # Checkpoint Configuration
    checkpoint_enabled: bool = Field(
        default=True, env="CHECKPOINT_ENABLED"
    )  # Enable/disable checkpointing
    checkpoint_cleanup_on_success: bool = Field(
        default=True, env="CHECKPOINT_CLEANUP_ON_SUCCESS"
    )  # Auto-cleanup checkpoint files after successful completion
    checkpoint_storage_path: Optional[str] = Field(
        default=None, env="CHECKPOINT_STORAGE_PATH"
    )  # Override checkpoint location (defaults to {subtitle_storage_path}/checkpoints)

    # Jellyfin Integration
    jellyfin_default_source_language: str = Field(
        default="en", env="JELLYFIN_DEFAULT_SOURCE_LANGUAGE"
    )
    jellyfin_default_target_language: Optional[str] = Field(
        default=None, env="JELLYFIN_DEFAULT_TARGET_LANGUAGE"
    )
    jellyfin_auto_translate: bool = Field(default=True, env="JELLYFIN_AUTO_TRANSLATE")

    # Scanner Configuration
    scanner_media_path: str = Field(default="/media", env="SCANNER_MEDIA_PATH")
    scanner_watch_recursive: bool = Field(default=True, env="SCANNER_WATCH_RECURSIVE")
    scanner_media_extensions: List[str] = Field(
        default=[".mp4", ".mkv", ".avi", ".mov", ".m4v", ".webm"],
        env="SCANNER_MEDIA_EXTENSIONS",
    )
    scanner_debounce_seconds: float = Field(default=2.0, env="SCANNER_DEBOUNCE_SECONDS")
    scanner_default_source_language: str = Field(
        default="en", env="SCANNER_DEFAULT_SOURCE_LANGUAGE"
    )
    scanner_default_target_language: Optional[str] = Field(
        default=None, env="SCANNER_DEFAULT_TARGET_LANGUAGE"
    )
    scanner_auto_translate: bool = Field(default=False, env="SCANNER_AUTO_TRANSLATE")

    # Scanner Webhook Configuration
    scanner_webhook_host: str = Field(default="0.0.0.0", env="SCANNER_WEBHOOK_HOST")
    scanner_webhook_port: int = Field(default=8001, env="SCANNER_WEBHOOK_PORT")

    @field_validator("scanner_media_extensions", mode="before")
    @classmethod
    def parse_media_extensions(cls, v: Union[str, List[str]]) -> List[str]:
        """
        Parse comma-separated string or return list as-is.

        Args:
            v: String with comma-separated extensions or list of extensions

        Returns:
            List of extension strings
        """
        if isinstance(v, str):
            # Split by comma and strip whitespace
            return [ext.strip() for ext in v.split(",") if ext.strip()]
        return v

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
