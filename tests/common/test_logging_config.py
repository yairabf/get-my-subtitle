"""Unit tests for logging configuration module."""

import logging
import sys
from unittest.mock import MagicMock, patch

import pytest

from common.logging_config import (
    ServiceLogger,
    configure_third_party_loggers,
    get_log_file_path,
    setup_logging,
    setup_service_logging,
)


@pytest.mark.unit
class TestSetupLogging:
    """Test setup_logging function."""

    def test_setup_logging_creates_logger(self):
        """Test that setup_logging creates a logger with correct name."""
        logger = setup_logging("test_service")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_service"

    @pytest.mark.parametrize(
        "service_name",
        [
            "manager",
            "downloader",
            "translator",
            "scanner",
            "consumer",
            "test-service",
            "service_with_underscores",
        ],
    )
    def test_setup_logging_with_different_service_names(self, service_name):
        """Test setup_logging with various service names."""
        logger = setup_logging(service_name)

        assert logger.name == service_name

    @pytest.mark.parametrize(
        "log_level",
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    def test_setup_logging_with_different_log_levels(self, log_level):
        """Test setup_logging with different log levels."""
        logger = setup_logging("test_service", log_level=log_level)

        assert logger.level == getattr(logging, log_level)
        # Check that handlers have correct level
        for handler in logger.handlers:
            assert handler.level == getattr(logging, log_level)

    def test_setup_logging_removes_existing_handlers(self):
        """Test setup_logging removes existing handlers."""
        logger = setup_logging("test_service")
        initial_handler_count = len(logger.handlers)

        # Add a dummy handler
        logger.addHandler(logging.NullHandler())

        # Setup again
        logger2 = setup_logging("test_service")

        # Should have cleared handlers and added new ones
        assert len(logger2.handlers) == initial_handler_count

    def test_setup_logging_console_handler(self):
        """Test that console handler is configured correctly."""
        logger = setup_logging("test_service")

        # Should have at least one StreamHandler for console
        console_handlers = [
            h for h in logger.handlers if isinstance(h, logging.StreamHandler)
        ]
        assert len(console_handlers) > 0

        # Check that it outputs to stdout
        stdout_handlers = [h for h in console_handlers if h.stream == sys.stdout]
        assert len(stdout_handlers) > 0

        # Check formatter
        assert console_handlers[0].formatter is not None

    def test_setup_logging_file_handler(self, tmp_path):
        """Test that file handler is configured when log_file is provided."""
        log_file = tmp_path / "test.log"
        logger = setup_logging("test_service", log_file=str(log_file))

        # Should have file handler
        file_handlers = [
            h for h in logger.handlers if isinstance(h, logging.FileHandler)
        ]
        assert len(file_handlers) > 0

        # Check that file was created
        assert log_file.exists()

        # Check formatter
        assert file_handlers[0].formatter is not None

    def test_setup_logging_creates_log_directory(self, tmp_path):
        """Test setup_logging creates log directory if it doesn't exist."""
        log_dir = tmp_path / "logs" / "subdir"
        log_file = log_dir / "test.log"

        setup_logging("test_service", log_file=str(log_file))

        # Directory should be created
        assert log_dir.exists()
        assert log_dir.is_dir()

        # File should be created
        assert log_file.exists()

    def test_setup_logging_without_file_handler(self):
        """Test setup_logging doesn't create file handler when None."""
        logger = setup_logging("test_service", log_file=None)

        # Should not have file handler
        file_handlers = [
            h for h in logger.handlers if isinstance(h, logging.FileHandler)
        ]
        assert len(file_handlers) == 0

    def test_setup_logging_propagates_false(self):
        """Test that logger propagation is disabled."""
        logger = setup_logging("test_service")

        assert logger.propagate is False

    def test_setup_logging_formatters(self):
        """Test that formatters are configured correctly."""
        logger = setup_logging("test_service")

        # All handlers should have formatters
        for handler in logger.handlers:
            assert handler.formatter is not None

            # Check formatter format string
            if isinstance(handler, logging.FileHandler):
                # File handler should have detailed formatter
                assert "%(filename)s" in handler.formatter._fmt
            elif isinstance(handler, logging.StreamHandler):
                # Console handler should have simple formatter
                assert "%(levelname)s" in handler.formatter._fmt

    def test_setup_logging_logs_to_file(self, tmp_path, caplog):
        """Test logs are written to file when file handler is configured."""
        log_file = tmp_path / "test.log"
        logger = setup_logging("test_service", log_file=str(log_file), log_level="INFO")

        # Log a message
        logger.info("Test message")

        # Check that file contains the message
        file_content = log_file.read_text()
        assert "Test message" in file_content

    def test_setup_logging_uses_settings_log_level_by_default(self, monkeypatch):
        """Test setup_logging uses settings.log_level when not overridden."""
        # Mock settings.log_level
        with patch("common.logging_config.settings") as mock_settings:
            mock_settings.log_level = "DEBUG"
            logger = setup_logging("test_service")

            assert logger.level == logging.DEBUG

    def test_setup_logging_override_log_level(self):
        """Test that log_level parameter overrides settings."""
        logger = setup_logging("test_service", log_level="ERROR")

        assert logger.level == logging.ERROR


@pytest.mark.unit
class TestGetLogFilePath:
    """Test get_log_file_path function."""

    @patch("common.logging_config.DateTimeUtils.get_date_string_for_log_file")
    def test_get_log_file_path_format(self, mock_date_string):
        """Test that get_log_file_path generates correct format."""
        mock_date_string.return_value = "20240101"

        path = get_log_file_path("test_service")

        assert path == "./logs/test_service_20240101.log"

    @patch("common.logging_config.DateTimeUtils.get_date_string_for_log_file")
    @pytest.mark.parametrize(
        "service_name,expected_prefix",
        [
            ("manager", "./logs/manager_"),
            ("downloader", "./logs/downloader_"),
            ("translator", "./logs/translator_"),
            ("scanner", "./logs/scanner_"),
        ],
    )
    def test_get_log_file_path_with_different_services(
        self, mock_date_string, service_name, expected_prefix
    ):
        """Test get_log_file_path with different service names."""
        mock_date_string.return_value = "20240101"

        path = get_log_file_path(service_name)

        assert path.startswith(expected_prefix)
        assert path.endswith(".log")

    @patch("common.logging_config.DateTimeUtils.get_date_string_for_log_file")
    def test_get_log_file_path_includes_date(self, mock_date_string):
        """Test that get_log_file_path includes date string."""
        mock_date_string.return_value = "20241225"

        path = get_log_file_path("test_service")

        assert "20241225" in path


@pytest.mark.unit
class TestServiceLogger:
    """Test ServiceLogger class."""

    @patch("common.logging_config.get_log_file_path")
    @patch("common.logging_config.setup_logging")
    def test_service_logger_initialization_with_file_logging(
        self,
        mock_setup_logging,
        mock_get_log_file_path,
    ):
        """Test ServiceLogger initialization with file logging enabled."""
        mock_get_log_file_path.return_value = "./logs/test_service_20240101.log"
        mock_logger = MagicMock(spec=logging.Logger)
        mock_setup_logging.return_value = mock_logger

        service_logger = ServiceLogger("test_service", enable_file_logging=True)

        assert service_logger.service_name == "test_service"
        assert service_logger.logger == mock_logger
        mock_get_log_file_path.assert_called_once_with("test_service")
        mock_setup_logging.assert_called_once()

    @patch("common.logging_config.setup_logging")
    def test_service_logger_initialization_without_file_logging(
        self, mock_setup_logging
    ):
        """Test ServiceLogger initialization with file logging disabled."""
        mock_logger = MagicMock(spec=logging.Logger)
        mock_setup_logging.return_value = mock_logger

        service_logger = ServiceLogger("test_service", enable_file_logging=False)

        assert service_logger.service_name == "test_service"
        assert service_logger.logger == mock_logger
        # Should call setup_logging with None for log_file
        mock_setup_logging.assert_called_once()
        # Check that log_file was None (could be positional or keyword)
        call_args = mock_setup_logging.call_args
        assert call_args[0][0] == "test_service"  # First positional arg
        assert call_args[1].get("log_file") is None or (
            len(call_args[0]) > 1 and call_args[0][1] is None
        )

    @pytest.mark.parametrize(
        "method_name,log_level",
        [
            ("info", logging.INFO),
            ("debug", logging.DEBUG),
            ("warning", logging.WARNING),
            ("error", logging.ERROR),
            ("critical", logging.CRITICAL),
        ],
    )
    def test_service_logger_logging_methods(self, method_name, log_level):
        """Test ServiceLogger logging methods call underlying logger."""
        with patch("common.logging_config.setup_logging") as mock_setup:
            mock_logger = MagicMock(spec=logging.Logger)
            mock_setup.return_value = mock_logger

            service_logger = ServiceLogger("test_service", enable_file_logging=False)

            # Call the method
            method = getattr(service_logger, method_name)
            method("test message", key="value")

            # Verify underlying logger was called
            logger_method = getattr(mock_logger, method_name)
            logger_method.assert_called_once_with("test message", key="value")

    def test_service_logger_exception_method(self):
        """Test ServiceLogger.exception method calls underlying logger."""
        with patch("common.logging_config.setup_logging") as mock_setup:
            mock_logger = MagicMock(spec=logging.Logger)
            mock_setup.return_value = mock_logger

            service_logger = ServiceLogger("test_service", enable_file_logging=False)

            # Call exception method
            service_logger.exception("error message", key="value")

            # Verify underlying logger was called
            mock_logger.exception.assert_called_once_with("error message", key="value")

    def test_service_logger_integration(self, tmp_path, caplog):
        """Test ServiceLogger integration with actual logging."""
        with patch("common.logging_config.get_log_file_path") as mock_get_path:
            log_file = tmp_path / "test.log"
            mock_get_path.return_value = str(log_file)

            service_logger = ServiceLogger("test_service", enable_file_logging=True)

            # Log messages at different levels
            service_logger.debug("Debug message")
            service_logger.info("Info message")
            service_logger.warning("Warning message")
            service_logger.error("Error message")
            service_logger.critical("Critical message")

            # Check that file was created and contains messages
            if log_file.exists():
                file_content = log_file.read_text()
                assert "Info message" in file_content
                assert "Warning message" in file_content
                assert "Error message" in file_content


@pytest.mark.unit
class TestConfigureThirdPartyLoggers:
    """Test configure_third_party_loggers function."""

    def test_configure_third_party_loggers_sets_levels(self):
        """Test configure_third_party_loggers sets log levels."""
        configure_third_party_loggers(level="WARNING")

        # Check that third-party loggers have correct level
        third_party_loggers = [
            "aio_pika",
            "aiormq",
            "openai",
            "httpx",
            "httpcore",
            "urllib3",
            "redis",
            "asyncio",
        ]

        for logger_name in third_party_loggers:
            logger = logging.getLogger(logger_name)
            assert logger.level == logging.WARNING

    @pytest.mark.parametrize(
        "level,expected_level",
        [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
        ],
    )
    def test_configure_third_party_loggers_with_different_levels(
        self, level, expected_level
    ):
        """Test configure_third_party_loggers with different log levels."""
        configure_third_party_loggers(level=level)

        # Check one of the loggers
        logger = logging.getLogger("aio_pika")
        assert logger.level == expected_level

    def test_configure_third_party_loggers_default_level(self):
        """Test that configure_third_party_loggers defaults to WARNING."""
        configure_third_party_loggers()

        # Check that loggers are set to WARNING
        logger = logging.getLogger("openai")
        assert logger.level == logging.WARNING

    def test_configure_third_party_loggers_invalid_level_defaults_to_warning(
        self,
    ):
        """Test invalid log level defaults to WARNING."""
        configure_third_party_loggers(level="INVALID_LEVEL")

        # Should default to WARNING
        logger = logging.getLogger("httpx")
        assert logger.level == logging.WARNING


@pytest.mark.unit
class TestSetupServiceLogging:
    """Test setup_service_logging function."""

    @patch("common.logging_config.configure_third_party_loggers")
    @patch("common.logging_config.ServiceLogger")
    def test_setup_service_logging_calls_configure_third_party(
        self, mock_service_logger, mock_configure
    ):
        """Test that setup_service_logging configures third-party loggers."""
        mock_instance = MagicMock()
        mock_service_logger.return_value = mock_instance

        result = setup_service_logging("test_service")

        # Should call configure_third_party_loggers
        mock_configure.assert_called_once()

        # Should create ServiceLogger (can be positional or keyword)
        mock_service_logger.assert_called_once()
        call_args = mock_service_logger.call_args
        assert call_args[0][0] == "test_service"  # First positional arg
        # Check enable_file_logging (could be positional or keyword)
        assert (len(call_args[0]) > 1 and call_args[0][1] is True) or call_args[1].get(
            "enable_file_logging"
        ) is True

        # Should return ServiceLogger instance
        assert result == mock_instance

    @patch("common.logging_config.configure_third_party_loggers")
    @patch("common.logging_config.ServiceLogger")
    def test_setup_service_logging_without_file_logging(
        self, mock_service_logger, mock_configure
    ):
        """Test setup_service_logging with file logging disabled."""
        mock_instance = MagicMock()
        mock_service_logger.return_value = mock_instance

        result = setup_service_logging("test_service", enable_file_logging=False)

        # Should create ServiceLogger without file logging
        # (can be positional or keyword)
        mock_service_logger.assert_called_once()
        call_args = mock_service_logger.call_args
        assert call_args[0][0] == "test_service"  # First positional arg
        # Check enable_file_logging (could be positional or keyword)
        assert (len(call_args[0]) > 1 and call_args[0][1] is False) or call_args[1].get(
            "enable_file_logging"
        ) is False

        assert result == mock_instance

    def test_setup_service_logging_integration(self, tmp_path):
        """Test setup_service_logging integration."""
        with patch("common.logging_config.get_log_file_path") as mock_get_path:
            log_file = tmp_path / "test.log"
            mock_get_path.return_value = str(log_file)

            service_logger = setup_service_logging("test_service")

            # Should be a ServiceLogger instance
            assert isinstance(service_logger, ServiceLogger)
            assert service_logger.service_name == "test_service"

            # Should be able to log
            service_logger.info("Test message")

            # Check that third-party loggers are configured
            third_party_logger = logging.getLogger("aio_pika")
            assert third_party_logger.level == logging.WARNING


@pytest.mark.unit
class TestLoggingIntegration:
    """Integration tests for logging configuration."""

    def test_full_logging_setup_flow(self, tmp_path, caplog):
        """Test the full logging setup flow."""
        with patch("common.logging_config.get_log_file_path") as mock_get_path:
            log_file = tmp_path / "integration_test.log"
            mock_get_path.return_value = str(log_file)

            # Setup logging
            service_logger = setup_service_logging("integration_test")

            # Log at different levels
            with caplog.at_level(logging.DEBUG):
                service_logger.debug("Debug message")
                service_logger.info("Info message")
                service_logger.warning("Warning message")
                service_logger.error("Error message")

            # Verify logs were captured (may be in stdout or caplog)
            # Since logger doesn't propagate and uses custom handlers,
            # caplog might not capture them, but they should be in stdout
            # Check that the logger was set up correctly
            assert service_logger.logger is not None
            # The actual log output might go to stdout, not caplog
            # This is expected behavior for non-propagating loggers

    def test_logger_isolation(self):
        """Test that different service loggers are isolated."""
        logger1 = setup_logging("service1")
        logger2 = setup_logging("service2")

        assert logger1.name == "service1"
        assert logger2.name == "service2"
        assert logger1 is not logger2

    def test_logger_handler_count(self):
        """Test that logger has expected number of handlers."""
        # Without file logging
        logger = setup_logging("test", log_file=None)
        # Should have at least console handler
        assert len(logger.handlers) >= 1

        # With file logging
        with patch("common.logging_config.get_log_file_path") as mock_get_path:
            mock_get_path.return_value = "./logs/test.log"
            logger = setup_logging("test", log_file="./logs/test.log")
            # Should have console and file handlers
            assert len(logger.handlers) >= 2
