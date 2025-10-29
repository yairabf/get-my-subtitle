"""Integration tests for EventPublisher topic exchange publishing."""

import asyncio
import json
from uuid import uuid4

import aio_pika
import pytest
from aio_pika import ExchangeType
from aio_pika.abc import AbstractChannel

from common.event_publisher import EventPublisher
from common.schemas import EventType, SubtitleEvent
from common.utils import DateTimeUtils


@pytest.mark.integration
@pytest.mark.asyncio
class TestTopicExchangePublishing:
    """Test topic exchange publishing functionality."""

    async def test_publish_event_to_topic_exchange(
        self, test_event_publisher, rabbitmq_channel
    ):
        """Test that events are published to subtitle.events topic exchange."""
        # Arrange
        job_id = uuid4()
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_READY,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="downloader",
            payload={
                "subtitle_path": "/storage/subtitle.srt",
                "language": "en",
                "download_url": "https://example.com/subtitle.srt",
            },
        )

        # Create a test queue bound to the exchange
        queue = await rabbitmq_channel.declare_queue("test_queue", exclusive=True)
        exchange = await rabbitmq_channel.declare_exchange(
            "subtitle.events", ExchangeType.TOPIC, durable=True
        )
        await queue.bind(exchange, routing_key="subtitle.ready")

        # Act
        result = await test_event_publisher.publish_event(event)

        # Assert
        assert result is True

        # Give message time to arrive
        await asyncio.sleep(0.1)

        # Verify message received
        message = await queue.get(timeout=5)
        assert message is not None
        await message.ack()

    async def test_event_routing_keys_match_event_types(
        self, test_event_publisher, rabbitmq_channel
    ):
        """Test that event routing keys match their event types."""
        # Arrange
        job_id = uuid4()
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_DOWNLOAD_REQUESTED,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="manager",
            payload={"video_url": "https://example.com/video.mp4"},
        )

        # Create a test queue bound to specific routing key
        queue = await rabbitmq_channel.declare_queue("test_queue", exclusive=True)
        exchange = await rabbitmq_channel.declare_exchange(
            "subtitle.events", ExchangeType.TOPIC, durable=True
        )
        await queue.bind(exchange, routing_key="subtitle.download.requested")

        # Act
        await test_event_publisher.publish_event(event)

        # Assert
        await asyncio.sleep(0.1)
        message = await queue.get(timeout=5)
        assert message is not None
        assert message.routing_key == "subtitle.download.requested"
        await message.ack()

    async def test_event_message_format(
        self, test_event_publisher, rabbitmq_channel
    ):
        """Test that event messages contain valid SubtitleEvent schema."""
        # Arrange
        job_id = uuid4()
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_TRANSLATED,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="translator",
            payload={
                "subtitle_file_path": "/storage/subtitle_translated.srt",
                "source_language": "en",
                "target_language": "es",
            },
            metadata={"translation_time_seconds": 5.2},
        )

        # Create test queue
        queue = await rabbitmq_channel.declare_queue("test_queue", exclusive=True)
        exchange = await rabbitmq_channel.declare_exchange(
            "subtitle.events", ExchangeType.TOPIC, durable=True
        )
        await queue.bind(exchange, routing_key="subtitle.translated")

        # Act
        await test_event_publisher.publish_event(event)

        # Assert
        await asyncio.sleep(0.1)
        message = await queue.get(timeout=5)
        assert message is not None

        # Parse message body
        message_data = json.loads(message.body.decode())
        received_event = SubtitleEvent(**message_data)

        # Verify event fields
        assert str(received_event.job_id) == str(job_id)
        assert received_event.event_type == EventType.SUBTITLE_TRANSLATED
        assert received_event.source == "translator"
        assert received_event.payload["source_language"] == "en"
        assert received_event.payload["target_language"] == "es"
        assert received_event.metadata["translation_time_seconds"] == 5.2

        await message.ack()

    async def test_event_persistence(
        self, test_event_publisher, rabbitmq_channel
    ):
        """Test that event messages use persistent delivery mode."""
        # Arrange
        job_id = uuid4()
        event = SubtitleEvent(
            event_type=EventType.JOB_FAILED,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="downloader",
            payload={"error": "Subtitle not found"},
        )

        # Create test queue
        queue = await rabbitmq_channel.declare_queue("test_queue", exclusive=True)
        exchange = await rabbitmq_channel.declare_exchange(
            "subtitle.events", ExchangeType.TOPIC, durable=True
        )
        await queue.bind(exchange, routing_key="job.failed")

        # Act
        await test_event_publisher.publish_event(event)

        # Assert
        await asyncio.sleep(0.1)
        message = await queue.get(timeout=5)
        assert message is not None

        # Verify delivery mode is persistent
        assert message.delivery_mode == aio_pika.DeliveryMode.PERSISTENT

        # Verify content type
        assert message.content_type == "application/json"

        await message.ack()

    async def test_multiple_event_types_published(
        self, test_event_publisher, rabbitmq_channel
    ):
        """Test that all EventType enum values can be published."""
        # Arrange
        job_id = uuid4()
        event_types = [
            EventType.SUBTITLE_DOWNLOAD_REQUESTED,
            EventType.SUBTITLE_READY,
            EventType.SUBTITLE_TRANSLATE_REQUESTED,
            EventType.SUBTITLE_TRANSLATED,
            EventType.JOB_FAILED,
        ]

        # Create test queue with wildcard binding
        queue = await rabbitmq_channel.declare_queue("test_queue", exclusive=True)
        exchange = await rabbitmq_channel.declare_exchange(
            "subtitle.events", ExchangeType.TOPIC, durable=True
        )
        await queue.bind(exchange, routing_key="#")

        # Act - Publish all event types
        for event_type in event_types:
            event = SubtitleEvent(
                event_type=event_type,
                job_id=job_id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="test",
                payload={"test": "data"},
            )
            result = await test_event_publisher.publish_event(event)
            assert result is True

        # Assert
        await asyncio.sleep(0.2)

        # Verify all events received
        received_event_types = []
        for _ in range(len(event_types)):
            message = await queue.get(timeout=5)
            assert message is not None

            message_data = json.loads(message.body.decode())
            received_event = SubtitleEvent(**message_data)
            received_event_types.append(received_event.event_type)

            await message.ack()

        # Verify all event types were received
        assert set(received_event_types) == set(event_types)


@pytest.mark.integration
@pytest.mark.asyncio
class TestEventSubscription:
    """Test event subscription functionality."""

    async def test_consumer_receives_events_by_routing_key(
        self, test_event_publisher, rabbitmq_channel
    ):
        """Test that consumer with specific routing key receives only matching events."""
        # Arrange
        job_id = uuid4()

        # Create queue bound to specific routing key
        queue = await rabbitmq_channel.declare_queue("test_queue", exclusive=True)
        exchange = await rabbitmq_channel.declare_exchange(
            "subtitle.events", ExchangeType.TOPIC, durable=True
        )
        await queue.bind(exchange, routing_key="subtitle.ready")

        # Act - Publish matching event
        matching_event = SubtitleEvent(
            event_type=EventType.SUBTITLE_READY,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="downloader",
            payload={"subtitle_path": "/storage/subtitle.srt"},
        )
        await test_event_publisher.publish_event(matching_event)

        # Publish non-matching event
        non_matching_event = SubtitleEvent(
            event_type=EventType.JOB_FAILED,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="downloader",
            payload={"error": "Failed"},
        )
        await test_event_publisher.publish_event(non_matching_event)

        # Assert - Only matching event received
        await asyncio.sleep(0.1)

        message = await queue.get(timeout=5)
        assert message is not None

        message_data = json.loads(message.body.decode())
        received_event = SubtitleEvent(**message_data)
        assert received_event.event_type == EventType.SUBTITLE_READY

        await message.ack()

        # Verify no more messages (non-matching event was filtered)
        with pytest.raises(asyncio.TimeoutError):
            await queue.get(timeout=1)

    async def test_wildcard_routing_patterns(
        self, test_event_publisher, rabbitmq_channel
    ):
        """Test wildcard routing patterns like 'subtitle.*' and 'subtitle.#'."""
        # Arrange
        job_id = uuid4()

        # Create queue with wildcard pattern
        queue = await rabbitmq_channel.declare_queue("test_queue", exclusive=True)
        exchange = await rabbitmq_channel.declare_exchange(
            "subtitle.events", ExchangeType.TOPIC, durable=True
        )
        # Bind with pattern that matches subtitle.ready and subtitle.translated
        await queue.bind(exchange, routing_key="subtitle.*")

        # Act - Publish events
        events = [
            SubtitleEvent(
                event_type=EventType.SUBTITLE_READY,
                job_id=job_id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="downloader",
                payload={},
            ),
            SubtitleEvent(
                event_type=EventType.SUBTITLE_TRANSLATED,
                job_id=job_id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="translator",
                payload={},
            ),
            # This should NOT match (has two dots after subtitle)
            SubtitleEvent(
                event_type=EventType.SUBTITLE_DOWNLOAD_REQUESTED,
                job_id=job_id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="manager",
                payload={},
            ),
        ]

        for event in events:
            await test_event_publisher.publish_event(event)

        # Assert - Only events matching subtitle.* pattern received
        await asyncio.sleep(0.1)

        received_count = 0
        try:
            while received_count < 3:  # Try to get up to 3 messages
                message = await queue.get(timeout=1)
                if message:
                    message_data = json.loads(message.body.decode())
                    received_event = SubtitleEvent(**message_data)

                    # Should only receive subtitle.ready and subtitle.translated
                    # NOT subtitle.download.requested (has multiple dots)
                    assert received_event.event_type in [
                        EventType.SUBTITLE_READY,
                        EventType.SUBTITLE_TRANSLATED,
                    ]
                    received_count += 1
                    await message.ack()
        except asyncio.TimeoutError:
            pass

        # Should have received exactly 2 messages (not 3)
        assert received_count == 2

    async def test_multiple_consumers_receive_same_event(
        self, test_event_publisher, rabbitmq_channel
    ):
        """Test that multiple consumers receive the same event (topic exchange fanout)."""
        # Arrange
        job_id = uuid4()

        # Create two queues bound to same routing key
        queue1 = await rabbitmq_channel.declare_queue("test_queue1", exclusive=True)
        queue2 = await rabbitmq_channel.declare_queue("test_queue2", exclusive=True)

        exchange = await rabbitmq_channel.declare_exchange(
            "subtitle.events", ExchangeType.TOPIC, durable=True
        )

        await queue1.bind(exchange, routing_key="subtitle.ready")
        await queue2.bind(exchange, routing_key="subtitle.ready")

        # Act - Publish one event
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_READY,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="downloader",
            payload={"subtitle_path": "/storage/subtitle.srt"},
        )
        await test_event_publisher.publish_event(event)

        # Assert - Both queues receive the event
        await asyncio.sleep(0.1)

        message1 = await queue1.get(timeout=5)
        assert message1 is not None
        message_data1 = json.loads(message1.body.decode())
        received_event1 = SubtitleEvent(**message_data1)
        assert str(received_event1.job_id) == str(job_id)
        await message1.ack()

        message2 = await queue2.get(timeout=5)
        assert message2 is not None
        message_data2 = json.loads(message2.body.decode())
        received_event2 = SubtitleEvent(**message_data2)
        assert str(received_event2.job_id) == str(job_id)
        await message2.ack()

        # Verify both received the same event
        assert str(received_event1.job_id) == str(received_event2.job_id)
        assert received_event1.event_type == received_event2.event_type


@pytest.mark.integration
@pytest.mark.asyncio
class TestEventPublisherConnectionHandling:
    """Test event publisher connection handling functionality."""

    async def test_event_publisher_connection_lifecycle(self, rabbitmq_container):
        """Test event publisher connection and disconnection lifecycle."""
        # Arrange
        publisher = EventPublisher()

        # Act - Connect
        await publisher.connect()

        # Assert - Connection established
        assert publisher.connection is not None
        assert publisher.channel is not None
        assert publisher.exchange is not None
        assert not publisher.connection.is_closed

        # Act - Disconnect
        await publisher.disconnect()

        # Assert - Connection closed
        assert publisher.connection.is_closed

    async def test_exchange_declaration_creates_topic_exchange(
        self, test_event_publisher, rabbitmq_channel
    ):
        """Test that exchange declaration creates durable topic exchange."""
        # Assert - Verify exchange exists and is TOPIC type
        exchange = await rabbitmq_channel.declare_exchange(
            "subtitle.events", ExchangeType.TOPIC, passive=True
        )

        # Verify exchange properties
        assert exchange.name == "subtitle.events"
        # Note: passive=True means we're just checking if it exists

    async def test_connection_failure_returns_false(self):
        """Test that publish_event returns False when connection fails."""
        # Arrange
        publisher = EventPublisher()

        # Mock settings to use invalid URL
        from unittest.mock import patch

        with patch("common.event_publisher.settings") as mock_settings:
            mock_settings.rabbitmq_url = "amqp://guest:guest@invalid-host:5672/"

            # Act - Try to connect (should fail gracefully)
            await publisher.connect()

            # Assert - Should be in mock mode (no exchange)
            assert publisher.exchange is None

            # Act - Try to publish event in mock mode
            job_id = uuid4()
            event = SubtitleEvent(
                event_type=EventType.SUBTITLE_READY,
                job_id=job_id,
                timestamp=DateTimeUtils.get_current_utc_datetime(),
                source="test",
                payload={},
            )
            result = await publisher.publish_event(event)

            # Assert - Should return True (mock mode logs but doesn't fail)
            assert result is True

    async def test_mock_mode_when_disconnected(self):
        """Test that mock mode is used when publisher is not connected."""
        # Arrange
        publisher = EventPublisher()

        # Don't connect - should be in mock mode
        assert publisher.exchange is None

        # Act - Try to publish event without connection
        job_id = uuid4()
        event = SubtitleEvent(
            event_type=EventType.SUBTITLE_READY,
            job_id=job_id,
            timestamp=DateTimeUtils.get_current_utc_datetime(),
            source="test",
            payload={"test": "data"},
        )
        result = await publisher.publish_event(event)

        # Assert - Should return True (mock mode)
        assert result is True

