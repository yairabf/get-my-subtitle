"""Tests for Manager's event consumer that processes SUBTITLE_REQUESTED events."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from aio_pika import Message

from common.schemas import EventType, SubtitleEvent, SubtitleStatus
from common.utils import DateTimeUtils
from manager.event_consumer import SubtitleEventConsumer


@pytest.fixture
def mock_redis_client():
    """Create mock Redis client."""
    with patch("manager.event_consumer.redis_client") as mock:
        mock.update_phase = AsyncMock()
        yield mock


@pytest.fixture
def mock_event_publisher():
    """Create mock event publisher."""
    with patch("manager.event_consumer.event_publisher") as mock:
        mock.publish_event = AsyncMock(return_value=True)
        yield mock


@pytest.fixture
def mock_orchestrator():
    """Create mock orchestrator."""
    with patch("manager.event_consumer.orchestrator") as mock:
        mock.enqueue_download_task = AsyncMock(return_value=True)
        mock.enqueue_translation_task = AsyncMock(return_value=True)
        yield mock


@pytest.fixture
def mock_rabbitmq_connection():
    """Create mock RabbitMQ connection."""
    mock_connection = AsyncMock()
    mock_channel = AsyncMock()
    mock_exchange = AsyncMock()
    mock_queue = AsyncMock()

    mock_connection.channel = AsyncMock(return_value=mock_channel)
    mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)
    mock_channel.declare_queue = AsyncMock(return_value=mock_queue)
    mock_queue.bind = AsyncMock()

    return mock_connection, mock_channel, mock_exchange, mock_queue


@pytest.fixture
def sample_subtitle_requested_event():
    """Create a sample SUBTITLE_REQUESTED event."""
    job_id = uuid4()
    event = SubtitleEvent(
        event_type=EventType.SUBTITLE_REQUESTED,
        job_id=job_id,
        timestamp=DateTimeUtils.get_current_utc_datetime(),
        source="scanner",
        payload={
            "video_url": "/media/movies/test_movie.mp4",
            "video_title": "Test Movie",
            "language": "en",
            "target_language": "es",
            "preferred_sources": ["opensubtitles"],
            "auto_translate": True,
        },
    )
    return event


class TestSubtitleEventConsumer:
    """Test suite for SubtitleEventConsumer class."""

    @pytest.mark.asyncio
    async def test_consumer_initialization(self):
        """Test that consumer initializes with correct default values."""
        consumer = SubtitleEventConsumer()

        assert consumer.connection is None
        assert consumer.channel is None
        assert consumer.exchange is None
        assert consumer.queue is None
        assert consumer.exchange_name == "subtitle.events"
        assert consumer.queue_name == "manager.subtitle.requests"
        assert consumer.routing_key == "subtitle.requested"
        assert consumer.is_consuming is False

    @pytest.mark.asyncio
    async def test_connect_success(self, mock_rabbitmq_connection):
        """Test successful connection to RabbitMQ."""
        mock_conn, mock_channel, mock_exchange, mock_queue = mock_rabbitmq_connection

        with patch(
            "manager.event_consumer.aio_pika.connect_robust",
            AsyncMock(return_value=mock_conn),
        ):
            consumer = SubtitleEventConsumer()
            await consumer.connect()

            # Verify connection established
            assert consumer.connection == mock_conn
            assert consumer.channel == mock_channel
            assert consumer.exchange == mock_exchange
            assert consumer.queue == mock_queue

            # Verify queue was bound to exchange with routing key
            # Note: Only binds to subtitle.requested - subtitle.translate.requested is handled by downloader
            assert mock_queue.bind.call_count == 1
            bind_call = mock_queue.bind.call_args
            assert bind_call[1]["routing_key"] == "subtitle.requested"

    @pytest.mark.asyncio
    async def test_connect_failure_mock_mode(self):
        """Test that connection failure enables mock mode."""
        with patch(
            "manager.event_consumer.aio_pika.connect_robust",
            AsyncMock(side_effect=Exception("Connection failed")),
        ):
            consumer = SubtitleEventConsumer()
            # Use minimal retries for faster test execution
            await consumer.connect(max_retries=1, retry_delay=0.01)

            # Should not raise exception, but log warning
            assert consumer.connection is None
            assert consumer.channel is None

    @pytest.mark.asyncio
    async def test_process_subtitle_request_success(
        self,
        mock_orchestrator,
        mock_redis_client,
        mock_event_publisher,
        sample_subtitle_requested_event,
    ):
        """Test successful processing of SUBTITLE_REQUESTED event."""
        consumer = SubtitleEventConsumer()

        await consumer._process_subtitle_request(sample_subtitle_requested_event)

        # Verify orchestrator was called with correct parameters
        mock_orchestrator.enqueue_download_task.assert_called_once()
        call_args = mock_orchestrator.enqueue_download_task.call_args

        # Verify request object
        request = call_args[0][0]
        assert request.video_url == "/media/movies/test_movie.mp4"
        assert request.video_title == "Test Movie"
        assert request.language == "en"
        assert request.target_language == "es"
        assert request.preferred_sources == ["opensubtitles"]

        # Verify job_id
        assert call_args[0][1] == sample_subtitle_requested_event.job_id

        # Redis should not be called on success (event-driven)
        mock_redis_client.update_phase.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_subtitle_request_enqueue_failure(
        self,
        mock_orchestrator,
        mock_redis_client,
        mock_event_publisher,
        sample_subtitle_requested_event,
    ):
        """Test handling of enqueue failure - should publish JOB_FAILED event."""
        mock_orchestrator.enqueue_download_task = AsyncMock(return_value=False)

        consumer = SubtitleEventConsumer()
        await consumer._process_subtitle_request(sample_subtitle_requested_event)

        # Verify JOB_FAILED event was published instead of direct Redis update
        mock_event_publisher.publish_event.assert_called_once()
        event = mock_event_publisher.publish_event.call_args[0][0]
        assert event.event_type == EventType.JOB_FAILED
        assert event.job_id == sample_subtitle_requested_event.job_id
        assert event.payload["error_message"] == "Failed to enqueue download task"

        # Verify NO direct Redis update (event-driven)
        mock_redis_client.update_phase.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_subtitle_request_exception_handling(
        self,
        mock_orchestrator,
        mock_redis_client,
        mock_event_publisher,
        sample_subtitle_requested_event,
    ):
        """Test exception handling during event processing - should publish JOB_FAILED event."""
        mock_orchestrator.enqueue_download_task = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        consumer = SubtitleEventConsumer()

        # Should not raise exception
        await consumer._process_subtitle_request(sample_subtitle_requested_event)

        # Verify JOB_FAILED event was published instead of direct Redis update
        mock_event_publisher.publish_event.assert_called_once()
        event = mock_event_publisher.publish_event.call_args[0][0]
        assert event.event_type == EventType.JOB_FAILED
        assert event.job_id == sample_subtitle_requested_event.job_id
        assert "error_message" in event.payload

        # Verify NO direct Redis update (event-driven)
        mock_redis_client.update_phase.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_subtitle_request_missing_payload_fields(
        self, mock_orchestrator, mock_redis_client, mock_event_publisher
    ):
        """Test handling of event with missing required payload fields - should publish JOB_FAILED event."""
        job_id = uuid4()
        incomplete_event = SubtitleEvent(
            event_type=EventType.SUBTITLE_REQUESTED,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="scanner",
            payload={
                "video_url": "/media/movies/test.mp4",
                # Missing video_title, language, etc.
            },
        )

        consumer = SubtitleEventConsumer()
        await consumer._process_subtitle_request(incomplete_event)

        # Verify JOB_FAILED event was published instead of direct Redis update
        mock_event_publisher.publish_event.assert_called_once()
        event = mock_event_publisher.publish_event.call_args[0][0]
        assert event.event_type == EventType.JOB_FAILED
        assert event.job_id == job_id
        assert "error_message" in event.payload

        # Verify NO direct Redis update (event-driven)
        mock_redis_client.update_phase.assert_not_called()

    @pytest.mark.asyncio
    async def test_message_callback_valid_event(
        self, mock_orchestrator, mock_redis_client, sample_subtitle_requested_event
    ):
        """Test message callback with valid event message."""
        consumer = SubtitleEventConsumer()

        # Create mock message
        mock_message = AsyncMock()
        mock_message.body = sample_subtitle_requested_event.model_dump_json().encode()
        mock_message.process = MagicMock()
        mock_message.process.return_value.__aenter__ = AsyncMock()
        mock_message.process.return_value.__aexit__ = AsyncMock()

        await consumer._on_message(mock_message)

        # Verify orchestrator was called
        mock_orchestrator.enqueue_download_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_message_callback_invalid_json(
        self, mock_orchestrator, mock_redis_client
    ):
        """Test message callback with invalid JSON."""
        consumer = SubtitleEventConsumer()

        # Create mock message with invalid JSON
        mock_message = AsyncMock()
        mock_message.body = b"invalid json {{"
        mock_message.process = MagicMock()
        mock_message.process.return_value.__aenter__ = AsyncMock()
        mock_message.process.return_value.__aexit__ = AsyncMock()

        # Should not raise exception
        await consumer._on_message(mock_message)

        # Orchestrator should not be called
        mock_orchestrator.enqueue_download_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_message_callback_wrong_event_type(
        self, mock_orchestrator, mock_redis_client
    ):
        """Test message callback with wrong event type (should be ignored)."""
        consumer = SubtitleEventConsumer()

        # Create event with wrong type
        wrong_event = SubtitleEvent(
            event_type=EventType.MEDIA_FILE_DETECTED,  # Wrong type
            job_id=uuid4(),
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="scanner",
            payload={},
        )

        mock_message = AsyncMock()
        mock_message.body = wrong_event.model_dump_json().encode()
        mock_message.process = MagicMock()
        mock_message.process.return_value.__aenter__ = AsyncMock()
        mock_message.process.return_value.__aexit__ = AsyncMock()

        await consumer._on_message(mock_message)

        # Should not process non-handled events (only SUBTITLE_REQUESTED and SUBTITLE_TRANSLATE_REQUESTED)
        mock_orchestrator.enqueue_download_task.assert_not_called()
        mock_orchestrator.enqueue_translation_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_disconnect(self, mock_rabbitmq_connection):
        """Test disconnect closes connection properly."""
        mock_conn, mock_channel, mock_exchange, mock_queue = mock_rabbitmq_connection
        mock_conn.is_closed = False

        with patch(
            "manager.event_consumer.aio_pika.connect_robust",
            AsyncMock(return_value=mock_conn),
        ):
            consumer = SubtitleEventConsumer()
            await consumer.connect()

            # Simulate consuming
            consumer.is_consuming = True

            await consumer.disconnect()

            # Verify connection was closed
            mock_conn.close.assert_called_once()
            assert consumer.is_consuming is False

    @pytest.mark.asyncio
    async def test_start_consuming_mock_mode(self):
        """Test that start_consuming handles mock mode gracefully."""
        with patch(
            "manager.event_consumer.aio_pika.connect_robust",
            AsyncMock(side_effect=Exception("Connection failed")),
        ), patch(
            "manager.event_consumer.settings.rabbitmq_reconnect_initial_delay",
            0.01,  # Use minimal delay for faster test execution
        ), patch.object(
            SubtitleEventConsumer,
            "connect",
            new_callable=AsyncMock,
        ) as mock_connect:
            # Make connect fail immediately without retries
            mock_connect.return_value = None

            consumer = SubtitleEventConsumer()
            # Don't connect, so consumer stays in mock mode

            # Should not raise exception
            task = asyncio.create_task(consumer.start_consuming())

            # Give it a moment
            await asyncio.sleep(0.1)

            # Stop consuming
            consumer.stop()
            await task

            # Should complete without errors

    @pytest.mark.asyncio
    async def test_handle_auto_translate_flag(
        self, mock_orchestrator, mock_redis_client, sample_subtitle_requested_event
    ):
        """Test that auto_translate flag is properly handled."""
        # Test with auto_translate = True
        sample_subtitle_requested_event.payload["auto_translate"] = True

        consumer = SubtitleEventConsumer()
        await consumer._process_subtitle_request(sample_subtitle_requested_event)

        # Verify enqueue_download_task was called (auto_translate is handled by orchestrator)
        mock_orchestrator.enqueue_download_task.assert_called_once()

        # Test with auto_translate = False
        mock_orchestrator.reset_mock()
        sample_subtitle_requested_event.payload["auto_translate"] = False

        await consumer._process_subtitle_request(sample_subtitle_requested_event)

        # Should still enqueue download task
        mock_orchestrator.enqueue_download_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_translation_request_success(
        self, mock_orchestrator, mock_redis_client, mock_event_publisher
    ):
        """Test successful processing of SUBTITLE_TRANSLATE_REQUESTED event."""
        job_id = uuid4()
        translation_event = SubtitleEvent(
            event_type=EventType.SUBTITLE_TRANSLATE_REQUESTED,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="downloader",
            payload={
                "subtitle_file_path": "/media/movies/movie.en.srt",
                "source_language": "en",
                "target_language": "he",
            },
        )

        consumer = SubtitleEventConsumer()
        await consumer._process_translation_request(translation_event)

        # Verify orchestrator was called with correct parameters
        mock_orchestrator.enqueue_translation_task.assert_called_once()
        call_args = mock_orchestrator.enqueue_translation_task.call_args

        assert call_args[0][0] == job_id
        assert call_args[0][1] == "/media/movies/movie.en.srt"
        assert call_args[0][2] == "en"
        assert call_args[0][3] == "he"

        # Redis should not be called (event-driven)
        mock_redis_client.update_phase.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_translation_request_missing_fields(
        self, mock_orchestrator, mock_redis_client, mock_event_publisher
    ):
        """Test handling of translation request with missing required fields."""
        job_id = uuid4()
        incomplete_event = SubtitleEvent(
            event_type=EventType.SUBTITLE_TRANSLATE_REQUESTED,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="downloader",
            payload={
                "subtitle_file_path": "/media/movies/movie.en.srt",
                # Missing source_language and target_language
            },
        )

        consumer = SubtitleEventConsumer()
        await consumer._process_translation_request(incomplete_event)

        # Verify JOB_FAILED event was published
        mock_event_publisher.publish_event.assert_called_once()
        event = mock_event_publisher.publish_event.call_args[0][0]
        assert event.event_type == EventType.JOB_FAILED
        assert event.job_id == job_id
        assert "error_message" in event.payload

        # Orchestrator should not be called
        mock_orchestrator.enqueue_translation_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_translation_request_enqueue_failure(
        self, mock_orchestrator, mock_redis_client, mock_event_publisher
    ):
        """Test handling of translation task enqueue failure."""
        job_id = uuid4()
        translation_event = SubtitleEvent(
            event_type=EventType.SUBTITLE_TRANSLATE_REQUESTED,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="downloader",
            payload={
                "subtitle_file_path": "/media/movies/movie.en.srt",
                "source_language": "en",
                "target_language": "he",
            },
        )

        mock_orchestrator.enqueue_translation_task = AsyncMock(return_value=False)

        consumer = SubtitleEventConsumer()
        await consumer._process_translation_request(translation_event)

        # Verify JOB_FAILED event was published
        mock_event_publisher.publish_event.assert_called_once()
        event = mock_event_publisher.publish_event.call_args[0][0]
        assert event.event_type == EventType.JOB_FAILED
        assert event.job_id == job_id
        assert event.payload["error_message"] == "Failed to enqueue translation task"

    @pytest.mark.asyncio
    async def test_message_callback_handles_translation_request(
        self, mock_orchestrator, mock_redis_client
    ):
        """Test message callback ignores SUBTITLE_TRANSLATE_REQUESTED events."""
        consumer = SubtitleEventConsumer()

        # Create translation request event
        translation_event = SubtitleEvent(
            event_type=EventType.SUBTITLE_TRANSLATE_REQUESTED,
            job_id=uuid4(),
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="downloader",
            payload={
                "subtitle_file_path": "/media/movies/movie.en.srt",
                "source_language": "en",
                "target_language": "he",
            },
        )

        mock_message = AsyncMock()
        mock_message.body = translation_event.model_dump_json().encode()
        mock_message.process = MagicMock()
        mock_message.process.return_value.__aenter__ = AsyncMock()
        mock_message.process.return_value.__aexit__ = AsyncMock()

        await consumer._on_message(mock_message)

        # Verify orchestrator was NOT called - downloader handles task creation directly
        # Manager only creates translation tasks via direct API calls (/subtitles/translate)
        mock_orchestrator.enqueue_translation_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_message_callback_ignores_other_event_types(
        self, mock_orchestrator, mock_redis_client
    ):
        """Test message callback ignores event types other than SUBTITLE_REQUESTED and SUBTITLE_TRANSLATE_REQUESTED."""
        consumer = SubtitleEventConsumer()

        # Create event with wrong type
        wrong_event = SubtitleEvent(
            event_type=EventType.MEDIA_FILE_DETECTED,  # Wrong type
            job_id=uuid4(),
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="scanner",
            payload={},
        )

        mock_message = AsyncMock()
        mock_message.body = wrong_event.model_dump_json().encode()
        mock_message.process = MagicMock()
        mock_message.process.return_value.__aenter__ = AsyncMock()
        mock_message.process.return_value.__aexit__ = AsyncMock()

        await consumer._on_message(mock_message)

        # Should not process non-handled events
        mock_orchestrator.enqueue_download_task.assert_not_called()
        mock_orchestrator.enqueue_translation_task.assert_not_called()
