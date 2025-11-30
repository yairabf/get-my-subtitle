"""Configuration management for the subtitle management system."""

from pathlib import Path
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

    # Duplicate Prevention Configuration
    duplicate_prevention_enabled: bool = Field(
        default=True, env="DUPLICATE_PREVENTION_ENABLED"
    )  # Enable/disable duplicate prevention
    duplicate_prevention_window_seconds: int = Field(
        default=3600, env="DUPLICATE_PREVENTION_WINDOW_SECONDS"
    )  # 1 hour default deduplication window

    # RabbitMQ Configuration
    rabbitmq_url: str = Field(
        default="amqp://admin:password@localhost:5672/", env="RABBITMQ_URL"
    )
    rabbitmq_translation_queue_routing_key: str = Field(
        default="subtitle.translation",
        env="RABBITMQ_TRANSLATION_QUEUE_ROUTING_KEY",
        description="RabbitMQ routing key for translation queue",
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
    translation_max_segments_per_chunk: int = Field(
        default=100, env="TRANSLATION_MAX_SEGMENTS_PER_CHUNK"
    )  # Maximum segments per chunk (100-200 recommended for GPT-4o-mini, up to 300-400 if server allows)

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

    # Subtitle Language Configuration
    subtitle_desired_language: str = Field(
        default="en", env="SUBTITLE_DESIRED_LANGUAGE"
    )  # The goal language (what you want to download)
    subtitle_fallback_language: str = Field(
        default="en", env="SUBTITLE_FALLBACK_LANGUAGE"
    )  # Fallback when desired isn't found (then translated to desired)

    # Jellyfin Integration
    jellyfin_auto_translate: bool = Field(default=True, env="JELLYFIN_AUTO_TRANSLATE")

    # Scanner Configuration
    scanner_media_path: str = Field(default="/media", env="SCANNER_MEDIA_PATH")
    scanner_watch_recursive: bool = Field(default=True, env="SCANNER_WATCH_RECURSIVE")
    scanner_media_extensions: List[str] = Field(
        default=[".mp4", ".mkv", ".avi", ".mov", ".m4v", ".webm"],
        env="SCANNER_MEDIA_EXTENSIONS",
    )
    scanner_debounce_seconds: float = Field(default=2.0, env="SCANNER_DEBOUNCE_SECONDS")
    scanner_auto_translate: bool = Field(default=False, env="SCANNER_AUTO_TRANSLATE")

    # Scanner Webhook Configuration
    scanner_webhook_host: str = Field(default="0.0.0.0", env="SCANNER_WEBHOOK_HOST")
    scanner_webhook_port: int = Field(default=8001, env="SCANNER_WEBHOOK_PORT")

    # Jellyfin WebSocket Configuration
    jellyfin_url: Optional[str] = Field(default=None, env="JELLYFIN_URL")
    jellyfin_api_key: Optional[str] = Field(default=None, env="JELLYFIN_API_KEY")
    jellyfin_websocket_enabled: bool = Field(
        default=True, env="JELLYFIN_WEBSOCKET_ENABLED"
    )
    jellyfin_websocket_reconnect_delay: float = Field(
        default=2.0, env="JELLYFIN_WEBSOCKET_RECONNECT_DELAY"
    )
    jellyfin_websocket_max_reconnect_delay: float = Field(
        default=300.0, env="JELLYFIN_WEBSOCKET_MAX_RECONNECT_DELAY"
    )
    jellyfin_fallback_sync_enabled: bool = Field(
        default=True, env="JELLYFIN_FALLBACK_SYNC_ENABLED"
    )
    jellyfin_fallback_sync_interval_hours: int = Field(
        default=24, env="JELLYFIN_FALLBACK_SYNC_INTERVAL_HOURS"
    )

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
        # Find .env file relative to project root (where docker-compose.yml is)
        # This file is in src/common/, so go up 2 levels to project root
        _project_root = Path(__file__).parent.parent.parent
        env_file = str(_project_root / ".env")
        case_sensitive = False


# Global settings instance
settings = Settings()
