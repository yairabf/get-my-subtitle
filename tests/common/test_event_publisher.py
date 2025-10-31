"""Unit tests for EventPublisher using AsyncMock."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import aio_pika
import pytest

from common.event_publisher import EventPublisher
from common.schemas import EventType, SubtitleEvent
from common.utils import DateTimeUtils


@pytest.mark.unit
@pytest.mark.asyncio
class TestEventPublisherConnection:
    """Test EventPublisher connection lifecycle and exchange declaration."""

    async def test_connect_establishes_rabbitmq_connection(
        self, mock_rabbitmq_connection, mock_rabbitmq_channel, mock_rabbitmq_exchange
    ):
        """Test that connect establishes RabbitMQ connection and declares exchange."""
        publisher = EventPublisher()

        with patch(
            "common.event_publisher.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )
            mock_rabbitmq_channel.declare_exchange = AsyncMock(
                return_value=mock_rabbitmq_exchange
            )

            await publisher.connect()

            assert publisher.connection is not None
            assert publisher.channel is not None
            assert publisher.exchange is not None

    async def test_connect_declares_topic_exchange_with_correct_params(
        self, mock_rabbitmq_connection, mock_rabbitmq_channel, mock_rabbitmq_exchange
    ):
        """Test that connect declares topic exchange with durable=True."""
        publisher = EventPublisher()

        with patch(
            "common.event_publisher.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )
            mock_rabbitmq_channel.declare_exchange = AsyncMock(
                return_value=mock_rabbitmq_exchange
            )

            await publisher.connect()

            # Verify exchange declaration
            mock_rabbitmq_channel.declare_exchange.assert_called_once_with(
                "subtitle.events",
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )

    async def test_disconnect_closes_connection(
        self, mock_rabbitmq_connection, mock_rabbitmq_channel, mock_rabbitmq_exchange
    ):
        """Test that disconnect closes RabbitMQ connection."""
        publisher = EventPublisher()

        with patch(
            "common.event_publisher.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )
            mock_rabbitmq_channel.declare_exchange = AsyncMock(
                return_value=mock_rabbitmq_exchange
            )

            await publisher.connect()
            await publisher.disconnect()

            mock_rabbitmq_connection.close.assert_called_once()

    async def test_connect_handles_connection_failure_gracefully(self):
        """Test that connect handles connection failures and enters mock mode."""
        publisher = EventPublisher()

        with patch(
            "common.event_publisher.aio_pika.connect_robust",
            side_effect=Exception("Connection failed"),
        ):
            # Should not raise exception - just log warning
            await publisher.connect()

            # Should be in mock mode
            assert publisher.connection is None
            assert publisher.channel is None
            assert publisher.exchange is None


@pytest.mark.unit
@pytest.mark.asyncio
class TestEventPublisherEventPublishing:
    """Test EventPublisher event publishing with routing keys."""

    async def test_publish_event_sends_message_to_exchange(
        self, mock_rabbitmq_connection, mock_rabbitmq_channel, mock_rabbitmq_exchange
    ):
        """Test that publish_event sends message to exchange with correct routing key."""
        publisher = EventPublisher()

        with patch(
            "common.event_publisher.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )
            mock_rabbitmq_channel.declare_exchange = AsyncMock(
                return_value=mock_rabbitmq_exchange
            )

            await publisher.connect()

            # Create event
            event = SubtitleEvent(
                event_type=EventType.SUBTITLE_READY,
                job_id=uuid4(),
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="downloader",
                payload={"subtitle_path": "/path/to/subtitle.srt"},
            )

            result = await publisher.publish_event(event)

            assert result is True
            mock_rabbitmq_exchange.publish.assert_called_once()

    async def test_publish_event_uses_event_type_as_routing_key(
        self, mock_rabbitmq_connection, mock_rabbitmq_channel, mock_rabbitmq_exchange
    ):
        """Test that publish_event uses event_type.value as routing key."""
        publisher = EventPublisher()

        with patch(
            "common.event_publisher.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )
            mock_rabbitmq_channel.declare_exchange = AsyncMock(
                return_value=mock_rabbitmq_exchange
            )

            await publisher.connect()

            # Create event
            event = SubtitleEvent(
                event_type=EventType.SUBTITLE_DOWNLOAD_REQUESTED,
                job_id=uuid4(),
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="manager",
                payload={"video_url": "https://example.com/video.mp4"},
            )

            await publisher.publish_event(event)

            # Verify routing key
            call_args = mock_rabbitmq_exchange.publish.call_args
            assert (
                call_args[1]["routing_key"]
                == EventType.SUBTITLE_DOWNLOAD_REQUESTED.value
            )

    async def test_publish_event_creates_persistent_message(
        self, mock_rabbitmq_connection, mock_rabbitmq_channel, mock_rabbitmq_exchange
    ):
        """Test that publish_event creates message with PERSISTENT delivery mode."""
        publisher = EventPublisher()

        with patch(
            "common.event_publisher.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )
            mock_rabbitmq_channel.declare_exchange = AsyncMock(
                return_value=mock_rabbitmq_exchange
            )

            await publisher.connect()

            event = SubtitleEvent(
                event_type=EventType.SUBTITLE_READY,
                job_id=uuid4(),
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="downloader",
                payload={},
            )

            await publisher.publish_event(event)

            # Verify message was created with PERSISTENT delivery mode
            call_args = mock_rabbitmq_exchange.publish.call_args
            message = call_args[0][0]
            assert message.delivery_mode == aio_pika.DeliveryMode.PERSISTENT

    async def test_publish_event_sets_json_content_type(
        self, mock_rabbitmq_connection, mock_rabbitmq_channel, mock_rabbitmq_exchange
    ):
        """Test that publish_event sets content_type to application/json."""
        publisher = EventPublisher()

        with patch(
            "common.event_publisher.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )
            mock_rabbitmq_channel.declare_exchange = AsyncMock(
                return_value=mock_rabbitmq_exchange
            )

            await publisher.connect()

            event = SubtitleEvent(
                event_type=EventType.JOB_FAILED,
                job_id=uuid4(),
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="downloader",
                payload={"error": "Download failed"},
            )

            await publisher.publish_event(event)

            # Verify content type
            call_args = mock_rabbitmq_exchange.publish.call_args
            message = call_args[0][0]
            assert message.content_type == "application/json"

    @pytest.mark.parametrize(
        "event_type",
        [
            EventType.SUBTITLE_DOWNLOAD_REQUESTED,
            EventType.SUBTITLE_READY,
            EventType.SUBTITLE_TRANSLATE_REQUESTED,
            EventType.SUBTITLE_TRANSLATED,
            EventType.JOB_FAILED,
        ],
    )
    async def test_publish_event_handles_all_event_types(
        self,
        mock_rabbitmq_connection,
        mock_rabbitmq_channel,
        mock_rabbitmq_exchange,
        event_type,
    ):
        """Test that publish_event handles all event types correctly."""
        publisher = EventPublisher()

        with patch(
            "common.event_publisher.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )
            mock_rabbitmq_channel.declare_exchange = AsyncMock(
                return_value=mock_rabbitmq_exchange
            )

            await publisher.connect()

            event = SubtitleEvent(
                event_type=event_type,
                job_id=uuid4(),
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="test",
                payload={},
            )

            result = await publisher.publish_event(event)

            assert result is True
            call_args = mock_rabbitmq_exchange.publish.call_args
            assert call_args[1]["routing_key"] == event_type.value


@pytest.mark.unit
@pytest.mark.asyncio
class TestEventPublisherMockMode:
    """Test EventPublisher graceful degradation when RabbitMQ unavailable."""

    async def test_publish_event_in_mock_mode_returns_true(self):
        """Test that publish_event in mock mode returns True without raising error."""
        publisher = EventPublisher()
        # Don't connect - publisher stays in mock mode

        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_READY,
            job_id=uuid4(),
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="downloader",
            payload={},
        )

        result = await publisher.publish_event(event)

        assert result is True

    async def test_publish_event_in_mock_mode_logs_warning(self, caplog):
        """Test that publish_event in mock mode logs appropriate warning."""
        publisher = EventPublisher()
        # Don't connect - publisher stays in mock mode

        job_id = uuid4()
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_READY,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="downloader",
            payload={},
        )

        await publisher.publish_event(event)

        # Verify warning was logged (check log records)
        assert any("Mock mode" in record.message for record in caplog.records)

    async def test_disconnect_when_not_connected_does_not_raise_error(self):
        """Test that disconnect when not connected doesn't raise error."""
        publisher = EventPublisher()
        # Don't connect

        # Should not raise error
        await publisher.disconnect()


@pytest.mark.unit
@pytest.mark.asyncio
class TestEventPublisherErrorHandling:
    """Test EventPublisher error scenarios and retry logic."""

    async def test_publish_event_returns_false_on_publishing_error(
        self, mock_rabbitmq_connection, mock_rabbitmq_channel, mock_rabbitmq_exchange
    ):
        """Test that publish_event returns False when publishing fails."""
        publisher = EventPublisher()

        with patch(
            "common.event_publisher.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )
            mock_rabbitmq_channel.declare_exchange = AsyncMock(
                return_value=mock_rabbitmq_exchange
            )

            await publisher.connect()

            # Make publish raise an error
            mock_rabbitmq_exchange.publish = AsyncMock(
                side_effect=Exception("Publish failed")
            )

            event = SubtitleEvent(
                event_type=EventType.SUBTITLE_READY,
                job_id=uuid4(),
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="downloader",
                payload={},
            )

            result = await publisher.publish_event(event)

            assert result is False

    async def test_publish_event_serializes_event_to_json(
        self, mock_rabbitmq_connection, mock_rabbitmq_channel, mock_rabbitmq_exchange
    ):
        """Test that publish_event properly serializes event to JSON."""
        publisher = EventPublisher()

        with patch(
            "common.event_publisher.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )
            mock_rabbitmq_channel.declare_exchange = AsyncMock(
                return_value=mock_rabbitmq_exchange
            )

            await publisher.connect()

            job_id = uuid4()
            event = SubtitleEvent(
                event_type=EventType.SUBTITLE_READY,
                job_id=job_id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="downloader",
                payload={"subtitle_path": "/path/to/sub.srt", "language": "en"},
            )

            await publisher.publish_event(event)

            # Verify message body contains serialized event
            call_args = mock_rabbitmq_exchange.publish.call_args
            message = call_args[0][0]
            body = message.body.decode()

            # Should be valid JSON containing event data
            assert str(job_id) in body
            assert "subtitle.ready" in body
            assert "downloader" in body

    async def test_exchange_name_is_subtitle_events(self):
        """Test that exchange name is set to subtitle.events."""
        publisher = EventPublisher()

        assert publisher.exchange_name == "subtitle.events"
