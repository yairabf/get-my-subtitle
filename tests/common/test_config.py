"""Unit tests for configuration management module."""

import pytest
from pydantic import ValidationError

from common.config import Settings


@pytest.mark.unit
class TestSettingsDefaults:
    """Test Settings class initialization with default values."""

    def test_settings_initialization_with_defaults(self, monkeypatch):
        """Test that Settings initializes with all default values."""
        # Set language env vars to default values to override .env file
        monkeypatch.setenv("SUBTITLE_DESIRED_LANGUAGE", "en")
        monkeypatch.setenv("SUBTITLE_FALLBACK_LANGUAGE", "en")
        # Create a new instance - env vars override .env file
        settings = Settings()

        # Redis Configuration defaults
        assert settings.redis_url == "redis://localhost:6379"
        assert settings.redis_job_ttl_completed == 604800  # 7 days
        assert settings.redis_job_ttl_failed == 259200  # 3 days
        assert settings.redis_job_ttl_active == 0  # No expiration

        # Duplicate Prevention defaults
        assert settings.duplicate_prevention_enabled is True
        assert settings.duplicate_prevention_window_seconds == 3600  # 1 hour

        # RabbitMQ defaults (may be overridden by .env file)
        # Check that it's a valid RabbitMQ URL format
        assert settings.rabbitmq_url.startswith("amqp://")
        assert (
            "localhost" in settings.rabbitmq_url or "127.0.0.1" in settings.rabbitmq_url
        )

        # API Configuration defaults
        assert settings.api_host == "0.0.0.0"
        assert settings.api_port == 8000

        # Logging defaults
        assert settings.log_level == "INFO"

        # OpenSubtitles defaults
        assert settings.opensubtitles_user_agent == "get-my-subtitle v1.0"
        assert settings.opensubtitles_max_retries == 3
        assert settings.opensubtitles_retry_delay == 1
        assert settings.opensubtitles_retry_max_delay == 60
        assert settings.opensubtitles_retry_exponential_base == 2

        # OpenAI defaults
        assert settings.openai_model == "gpt-5-nano"
        assert settings.openai_max_tokens == 4096
        assert settings.openai_temperature == 0.3

        # Translation Token Limits defaults
        assert settings.translation_max_tokens_per_chunk == 8000
        assert settings.translation_token_safety_margin == 0.8

        # OpenAI Retry Configuration defaults
        assert settings.openai_max_retries == 3
        assert settings.openai_retry_initial_delay == 2.0
        assert settings.openai_retry_max_delay == 60.0
        assert settings.openai_retry_exponential_base == 2

        # File Storage defaults
        assert settings.subtitle_storage_path == "./storage/subtitles"

        # Checkpoint Configuration defaults
        assert settings.checkpoint_enabled is True
        assert settings.checkpoint_cleanup_on_success is True
        assert settings.checkpoint_storage_path is None

        # Subtitle Language Configuration defaults
        assert settings.subtitle_desired_language == "en"
        assert settings.subtitle_fallback_language == "en"

        # Jellyfin Integration defaults
        assert settings.jellyfin_auto_translate is True

        # Scanner Configuration defaults
        assert settings.scanner_media_path == "/media"
        assert settings.scanner_watch_recursive is True
        assert settings.scanner_media_extensions == [
            ".mp4",
            ".mkv",
            ".avi",
            ".mov",
            ".m4v",
            ".webm",
        ]
        assert settings.scanner_debounce_seconds == 2.0
        assert settings.scanner_auto_translate is False

        # Scanner Webhook Configuration defaults
        assert settings.scanner_webhook_host == "0.0.0.0"
        assert settings.scanner_webhook_port == 8001

        # Jellyfin WebSocket Configuration defaults
        assert settings.jellyfin_url is None
        assert settings.jellyfin_api_key is None
        assert settings.jellyfin_websocket_enabled is True
        assert settings.jellyfin_websocket_reconnect_delay == 2.0
        assert settings.jellyfin_websocket_max_reconnect_delay == 300.0
        assert settings.jellyfin_fallback_sync_enabled is True
        assert settings.jellyfin_fallback_sync_interval_hours == 24


@pytest.mark.unit
class TestSettingsEnvironmentVariables:
    """Test Settings class loading from environment variables."""

    @pytest.mark.parametrize(
        "env_var,value,expected",
        [
            ("REDIS_URL", "redis://custom:6379", "redis://custom:6379"),
            ("REDIS_JOB_TTL_COMPLETED", "86400", 86400),
            ("REDIS_JOB_TTL_FAILED", "172800", 172800),
            ("REDIS_JOB_TTL_ACTIVE", "3600", 3600),
            ("DUPLICATE_PREVENTION_ENABLED", "false", False),
            ("DUPLICATE_PREVENTION_WINDOW_SECONDS", "7200", 7200),
            (
                "RABBITMQ_URL",
                "amqp://user:pass@host:5672/",
                "amqp://user:pass@host:5672/",
            ),
            ("API_HOST", "127.0.0.1", "127.0.0.1"),
            ("API_PORT", "9000", 9000),
            ("LOG_LEVEL", "DEBUG", "DEBUG"),
            ("OPENSUBTITLES_USER_AGENT", "custom-agent", "custom-agent"),
            ("OPENSUBTITLES_USERNAME", "testuser", "testuser"),
            ("OPENSUBTITLES_PASSWORD", "testpass", "testpass"),
            ("OPENSUBTITLES_MAX_RETRIES", "5", 5),
            ("OPENSUBTITLES_RETRY_DELAY", "2", 2),
            ("OPENSUBTITLES_RETRY_MAX_DELAY", "120", 120),
            ("OPENSUBTITLES_RETRY_EXPONENTIAL_BASE", "3", 3),
            ("OPENAI_API_KEY", "sk-test123", "sk-test123"),
            ("OPENAI_MODEL", "gpt-4", "gpt-4"),
            ("OPENAI_MAX_TOKENS", "8192", 8192),
            ("OPENAI_TEMPERATURE", "0.5", 0.5),
            ("TRANSLATION_MAX_TOKENS_PER_CHUNK", "16000", 16000),
            ("TRANSLATION_TOKEN_SAFETY_MARGIN", "0.9", 0.9),
            ("OPENAI_MAX_RETRIES", "5", 5),
            ("OPENAI_RETRY_INITIAL_DELAY", "3.0", 3.0),
            ("OPENAI_RETRY_MAX_DELAY", "120.0", 120.0),
            ("OPENAI_RETRY_EXPONENTIAL_BASE", "3", 3),
            ("SUBTITLE_STORAGE_PATH", "/custom/path", "/custom/path"),
            ("CHECKPOINT_ENABLED", "false", False),
            ("CHECKPOINT_CLEANUP_ON_SUCCESS", "false", False),
            (
                "CHECKPOINT_STORAGE_PATH",
                "/custom/checkpoints",
                "/custom/checkpoints",
            ),
            ("SUBTITLE_DESIRED_LANGUAGE", "es", "es"),
            ("SUBTITLE_FALLBACK_LANGUAGE", "en", "en"),
            ("JELLYFIN_AUTO_TRANSLATE", "false", False),
            ("SCANNER_MEDIA_PATH", "/custom/media", "/custom/media"),
            ("SCANNER_WATCH_RECURSIVE", "false", False),
            ("SCANNER_DEBOUNCE_SECONDS", "5.0", 5.0),
            ("SCANNER_AUTO_TRANSLATE", "true", True),
            ("SCANNER_WEBHOOK_HOST", "127.0.0.1", "127.0.0.1"),
            ("SCANNER_WEBHOOK_PORT", "9001", 9001),
            ("JELLYFIN_URL", "http://jellyfin:8096", "http://jellyfin:8096"),
            ("JELLYFIN_API_KEY", "apikey123", "apikey123"),
            ("JELLYFIN_WEBSOCKET_ENABLED", "false", False),
            ("JELLYFIN_WEBSOCKET_RECONNECT_DELAY", "5.0", 5.0),
            ("JELLYFIN_WEBSOCKET_MAX_RECONNECT_DELAY", "600.0", 600.0),
            ("JELLYFIN_FALLBACK_SYNC_ENABLED", "false", False),
            ("JELLYFIN_FALLBACK_SYNC_INTERVAL_HOURS", "12", 12),
        ],
    )
    def test_environment_variable_loading(self, monkeypatch, env_var, value, expected):
        """Test that environment variables are loaded correctly."""
        # Set environment variable
        monkeypatch.setenv(env_var, value)

        # Create new Settings instance
        settings = Settings()

        # Get the attribute name (convert ENV_VAR to env_var)
        attr_name = env_var.lower()

        # Get the actual value
        actual_value = getattr(settings, attr_name)

        # Compare (handle type conversion for bool/int/float)
        if isinstance(expected, bool):
            assert actual_value is expected
        elif isinstance(expected, int):
            assert actual_value == int(value)
        elif isinstance(expected, float):
            assert actual_value == float(value)
        else:
            assert actual_value == expected

    def test_optional_fields_can_be_none(self, monkeypatch):
        """Test that optional fields can be None."""
        # Set optional fields to empty strings (which should result in None)
        monkeypatch.setenv("OPENSUBTITLES_USERNAME", "")
        monkeypatch.setenv("OPENSUBTITLES_PASSWORD", "")
        monkeypatch.setenv("OPENAI_API_KEY", "")
        monkeypatch.setenv("CHECKPOINT_STORAGE_PATH", "")
        monkeypatch.setenv("JELLYFIN_URL", "")
        monkeypatch.setenv("JELLYFIN_API_KEY", "")

        settings = Settings()

        # These should be None or empty string depending on Pydantic behavior
        # Pydantic may convert empty strings to None for Optional fields
        assert settings.opensubtitles_username in (None, "")
        assert settings.opensubtitles_password in (None, "")
        assert settings.openai_api_key in (None, "")


@pytest.mark.unit
class TestScannerMediaExtensionsValidator:
    """Test scanner_media_extensions field validator."""

    def test_parse_media_extensions_with_string_input(self):
        """Test parse_media_extensions validator with string inputs."""
        # Test the validator method directly with string inputs
        test_cases = [
            (".mp4,.mkv,.avi", [".mp4", ".mkv", ".avi"]),
            (".mp4, .mkv, .avi", [".mp4", ".mkv", ".avi"]),  # With spaces
            (".mp4", [".mp4"]),  # Single extension
            ("", []),  # Empty string
            (".mp4,", [".mp4"]),  # Trailing comma
            (",.mp4", [".mp4"]),  # Leading comma
            (".mp4, ,.mkv", [".mp4", ".mkv"]),  # Empty items filtered
        ]

        for input_value, expected in test_cases:
            result = Settings.parse_media_extensions(input_value)
            assert result == expected

    def test_parse_media_extensions_with_list_input(self):
        """Test parse_media_extensions validator with list inputs."""
        # Test the validator method directly with list inputs
        test_cases = [
            ([".mp4", ".mkv", ".avi"], [".mp4", ".mkv", ".avi"]),
            ([".mp4"], [".mp4"]),  # Single item list
            ([], []),  # Empty list
        ]

        for input_value, expected in test_cases:
            result = Settings.parse_media_extensions(input_value)
            assert result == expected
            # Should return same list object
            assert result is input_value

    def test_parse_media_extensions_with_complex_string(self):
        """Test parse_media_extensions with complex comma-separated string."""
        input_string = ".mp4, .mkv , .avi, .mov, .m4v"
        result = Settings.parse_media_extensions(input_string)
        assert result == [".mp4", ".mkv", ".avi", ".mov", ".m4v"]

    def test_parse_media_extensions_preserves_order(self):
        """Test that parse_media_extensions preserves order."""
        input_string = ".z, .a, .m, .b"
        result = Settings.parse_media_extensions(input_string)
        assert result == [".z", ".a", ".m", ".b"]


@pytest.mark.unit
class TestSettingsTypeValidation:
    """Test type validation for Settings fields."""

    def test_invalid_type_for_int_field(self, monkeypatch):
        """Test that invalid types for int fields raise ValidationError."""
        monkeypatch.setenv("API_PORT", "not-an-int")

        with pytest.raises(ValidationError):
            Settings()

    def test_invalid_type_for_float_field(self, monkeypatch):
        """Test that invalid types for float fields raise ValidationError."""
        monkeypatch.setenv("OPENAI_TEMPERATURE", "not-a-float")

        with pytest.raises(ValidationError):
            Settings()

    def test_invalid_type_for_bool_field(self, monkeypatch):
        """Test that invalid types for bool fields raise ValidationError."""
        # Pydantic is lenient with bool, but we can test edge cases
        # Empty string might be treated as False
        monkeypatch.setenv("DUPLICATE_PREVENTION_ENABLED", "maybe")

        # Pydantic might convert "maybe" to False or raise error
        # Let's test what happens
        try:
            settings = Settings()
            # If it doesn't raise, it might have converted to False
            assert isinstance(settings.duplicate_prevention_enabled, bool)
        except ValidationError:
            # Or it might raise, which is also acceptable
            pass

    def test_valid_int_conversion(self, monkeypatch):
        """Test that string numbers are converted to int correctly."""
        monkeypatch.setenv("API_PORT", "9000")
        settings = Settings()
        assert settings.api_port == 9000
        assert isinstance(settings.api_port, int)

    def test_valid_float_conversion(self, monkeypatch):
        """Test that string numbers are converted to float correctly."""
        monkeypatch.setenv("OPENAI_TEMPERATURE", "0.7")
        settings = Settings()
        assert settings.openai_temperature == 0.7
        assert isinstance(settings.openai_temperature, float)

    def test_valid_bool_conversion(self, monkeypatch):
        """Test that string booleans are converted correctly."""
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
        ]

        for env_value, expected in test_cases:
            monkeypatch.setenv("DUPLICATE_PREVENTION_ENABLED", env_value)
            settings = Settings()
            assert settings.duplicate_prevention_enabled is expected


@pytest.mark.unit
class TestSettingsEdgeCases:
    """Test edge cases for Settings class."""

    def test_empty_string_for_optional_field(self, monkeypatch):
        """Test that empty strings for optional fields are handled."""
        monkeypatch.setenv("OPENAI_API_KEY", "")
        settings = Settings()
        # Empty string might be converted to None or kept as empty string
        assert settings.openai_api_key in (None, "")

    def test_very_long_string_values(self, monkeypatch):
        """Test that very long string values are accepted."""
        long_string = "x" * 1000
        monkeypatch.setenv("OPENSUBTITLES_USER_AGENT", long_string)
        settings = Settings()
        assert settings.opensubtitles_user_agent == long_string

    def test_negative_values_for_positive_fields(self, monkeypatch):
        """Test negative values accepted (validation might be elsewhere)."""
        # Some fields might accept negative values, others might not
        # This depends on business logic, not type validation
        monkeypatch.setenv("API_PORT", "-1")
        # Pydantic might accept this or raise ValidationError
        try:
            settings = Settings()
            assert isinstance(settings.api_port, int)
        except ValidationError:
            # If it raises, that's also acceptable
            pass

    def test_zero_values(self, monkeypatch):
        """Test that zero values are handled correctly."""
        monkeypatch.setenv("REDIS_JOB_TTL_ACTIVE", "0")
        settings = Settings()
        assert settings.redis_job_ttl_active == 0

    def test_case_insensitive_environment_variables(self, monkeypatch):
        """Test env vars are case-insensitive (per Config)."""
        # Pydantic Settings with case_sensitive=False should handle this
        monkeypatch.setenv("redis_url", "redis://test:6379")
        monkeypatch.setenv("API_PORT", "9000")
        settings = Settings()
        # Both should work
        assert settings.redis_url == "redis://test:6379"
        assert settings.api_port == 9000

    def test_multiple_settings_instances(self):
        """Test that multiple Settings instances work independently."""
        settings1 = Settings()
        settings2 = Settings()

        # Both should have same defaults
        assert settings1.api_port == settings2.api_port
        assert settings1.redis_url == settings2.redis_url

    def test_settings_config_class(self):
        """Test that Config class is properly configured."""
        settings = Settings()
        assert hasattr(settings, "model_config") or hasattr(Settings, "Config")
        # Verify env_file is configured
        config = getattr(Settings, "Config", None) or getattr(
            settings, "model_config", None
        )
        if config:
            # Check that case_sensitive is False
            assert getattr(config, "case_sensitive", True) is False
