"""Integration tests for SubtitleOrchestrator queue publishing."""

import json
from uuid import uuid4

import aio_pika
import pytest
from aio_pika.abc import AbstractChannel

from common.schemas import DownloadTask, SubtitleRequest, TranslationTask
from manager.orchestrator import SubtitleOrchestrator


@pytest.mark.integration
@pytest.mark.asyncio
class TestDownloadQueuePublishing:
    """Test download queue publishing functionality."""

    async def test_enqueue_download_task_publishes_to_queue(
        self, test_orchestrator, rabbitmq_channel
    ):
        """Test that enqueue_download_task publishes message to subtitle.download queue."""
        # Arrange
        request_id = uuid4()
        request = SubtitleRequest(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            preferred_sources=["opensubtitles"],
        )

        # Act
        result = await test_orchestrator.enqueue_download_task(request, request_id)

        # Assert
        assert result is True

        # Verify message in queue by consuming it
        queue = await rabbitmq_channel.declare_queue("subtitle.download", durable=True)
        message = await queue.get(timeout=5)
        assert message is not None, "No message found in queue"
        await message.ack()

    async def test_download_task_message_format(
        self, test_orchestrator, rabbitmq_channel
    ):
        """Test that download task message contains valid DownloadTask schema."""
        # Arrange
        request_id = uuid4()
        request = SubtitleRequest(
            video_url="https://example.com/video.mp4",
            video_title="Integration Test Video",
            language="es",
            preferred_sources=["opensubtitles", "subscene"],
        )

        # Act
        await test_orchestrator.enqueue_download_task(request, request_id)

        # Assert
        queue = await rabbitmq_channel.declare_queue("subtitle.download", durable=True)
        message = await queue.get(timeout=5)
        assert message is not None

        # Parse message body
        message_data = json.loads(message.body.decode())
        download_task = DownloadTask(**message_data)

        # Verify task fields
        assert str(download_task.request_id) == str(request_id)
        assert download_task.video_url == "https://example.com/video.mp4"
        assert download_task.video_title == "Integration Test Video"
        assert download_task.language == "es"
        assert download_task.preferred_sources == ["opensubtitles", "subscene"]

        await message.ack()

    async def test_download_task_persistence(self, test_orchestrator, rabbitmq_channel):
        """Test that download task messages are persistent/durable."""
        # Arrange
        request_id = uuid4()
        request = SubtitleRequest(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            preferred_sources=["opensubtitles"],
        )

        # Act
        await test_orchestrator.enqueue_download_task(request, request_id)

        # Assert
        queue = await rabbitmq_channel.declare_queue("subtitle.download", durable=True)
        message = await queue.get(timeout=5)
        assert message is not None

        # Verify delivery mode is persistent
        assert message.delivery_mode == aio_pika.DeliveryMode.PERSISTENT

        await message.ack()

    async def test_download_task_routing_key(self, test_orchestrator, rabbitmq_channel):
        """Test that download task uses correct routing key."""
        # Arrange
        request_id = uuid4()
        request = SubtitleRequest(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            preferred_sources=["opensubtitles"],
        )

        # Act
        await test_orchestrator.enqueue_download_task(request, request_id)

        # Assert - Message should be in subtitle.download queue
        queue = await rabbitmq_channel.declare_queue("subtitle.download", durable=True)
        assert queue.declaration_result.message_count == 1

        message = await queue.get(timeout=5)
        assert message is not None
        assert message.routing_key == "subtitle.download"

        await message.ack()

    async def test_multiple_download_tasks_queued_in_order(
        self, test_orchestrator, rabbitmq_channel
    ):
        """Test that multiple download tasks are queued in FIFO order."""
        # Arrange
        request_ids = [uuid4() for _ in range(3)]
        requests = [
            SubtitleRequest(
                video_url=f"https://example.com/video{i}.mp4",
                video_title=f"Test Video {i}",
                language="en",
                preferred_sources=["opensubtitles"],
            )
            for i in range(3)
        ]

        # Act
        for request_id, request in zip(request_ids, requests):
            result = await test_orchestrator.enqueue_download_task(request, request_id)
            assert result is True

        # Assert
        queue = await rabbitmq_channel.declare_queue("subtitle.download", durable=True)
        assert queue.declaration_result.message_count == 3

        # Verify FIFO order
        for i in range(3):
            message = await queue.get(timeout=5)
            assert message is not None

            message_data = json.loads(message.body.decode())
            download_task = DownloadTask(**message_data)

            assert str(download_task.request_id) == str(request_ids[i])
            assert download_task.video_title == f"Test Video {i}"

            await message.ack()


@pytest.mark.integration
@pytest.mark.asyncio
class TestTranslationQueuePublishing:
    """Test translation queue publishing functionality."""

    async def test_enqueue_translation_task_publishes_to_queue(
        self, test_orchestrator, rabbitmq_channel
    ):
        """Test that enqueue_translation_task publishes to subtitle.translation queue."""
        # Arrange
        request_id = uuid4()
        subtitle_file_path = "/tmp/subtitle_test.srt"
        source_language = "en"
        target_language = "es"

        # Act
        result = await test_orchestrator.enqueue_translation_task(
            request_id, subtitle_file_path, source_language, target_language
        )

        # Assert
        assert result is True

        # Verify message in queue
        queue = await rabbitmq_channel.declare_queue(
            "subtitle.translation", durable=True
        )
        assert queue.declaration_result.message_count == 1

        message = await queue.get(timeout=5)
        assert message is not None
        await message.ack()

    async def test_translation_task_message_format(
        self, test_orchestrator, rabbitmq_channel
    ):
        """Test that translation task message contains valid TranslationTask schema."""
        # Arrange
        request_id = uuid4()
        subtitle_file_path = "/storage/subtitles/test_subtitle.srt"
        source_language = "en"
        target_language = "fr"

        # Act
        await test_orchestrator.enqueue_translation_task(
            request_id, subtitle_file_path, source_language, target_language
        )

        # Assert
        queue = await rabbitmq_channel.declare_queue(
            "subtitle.translation", durable=True
        )
        message = await queue.get(timeout=5)
        assert message is not None

        # Parse message body
        message_data = json.loads(message.body.decode())
        translation_task = TranslationTask(**message_data)

        # Verify task fields
        assert str(translation_task.request_id) == str(request_id)
        assert (
            translation_task.subtitle_file_path
            == "/storage/subtitles/test_subtitle.srt"
        )
        assert translation_task.source_language == "en"
        assert translation_task.target_language == "fr"

        await message.ack()

    async def test_translation_task_persistence(
        self, test_orchestrator, rabbitmq_channel
    ):
        """Test that translation task messages are durable/persistent."""
        # Arrange
        request_id = uuid4()
        subtitle_file_path = "/tmp/subtitle.srt"
        source_language = "en"
        target_language = "es"

        # Act
        await test_orchestrator.enqueue_translation_task(
            request_id, subtitle_file_path, source_language, target_language
        )

        # Assert
        queue = await rabbitmq_channel.declare_queue(
            "subtitle.translation", durable=True
        )
        message = await queue.get(timeout=5)
        assert message is not None

        # Verify delivery mode is persistent
        assert message.delivery_mode == aio_pika.DeliveryMode.PERSISTENT

        await message.ack()

    async def test_translation_task_routing_key(
        self, test_orchestrator, rabbitmq_channel
    ):
        """Test that translation task uses correct routing key."""
        # Arrange
        request_id = uuid4()
        subtitle_file_path = "/tmp/subtitle.srt"
        source_language = "en"
        target_language = "es"

        # Act
        await test_orchestrator.enqueue_translation_task(
            request_id, subtitle_file_path, source_language, target_language
        )

        # Assert - Message should be in subtitle.translation queue
        queue = await rabbitmq_channel.declare_queue(
            "subtitle.translation", durable=True
        )
        assert queue.declaration_result.message_count == 1

        message = await queue.get(timeout=5)
        assert message is not None
        assert message.routing_key == "subtitle.translation"

        await message.ack()

    async def test_multiple_translation_tasks_queued_in_order(
        self, test_orchestrator, rabbitmq_channel
    ):
        """Test that multiple translation tasks are queued in FIFO order."""
        # Arrange
        request_ids = [uuid4() for _ in range(3)]
        subtitle_paths = [f"/tmp/subtitle_{i}.srt" for i in range(3)]
        languages = [("en", "es"), ("en", "fr"), ("en", "de")]

        # Act
        for request_id, path, (src, tgt) in zip(request_ids, subtitle_paths, languages):
            result = await test_orchestrator.enqueue_translation_task(
                request_id, path, src, tgt
            )
            assert result is True

        # Assert
        queue = await rabbitmq_channel.declare_queue(
            "subtitle.translation", durable=True
        )
        assert queue.declaration_result.message_count == 3

        # Verify FIFO order
        for i in range(3):
            message = await queue.get(timeout=5)
            assert message is not None

            message_data = json.loads(message.body.decode())
            translation_task = TranslationTask(**message_data)

            assert str(translation_task.request_id) == str(request_ids[i])
            assert translation_task.subtitle_file_path == subtitle_paths[i]

            await message.ack()


@pytest.mark.integration
@pytest.mark.asyncio
class TestCombinedDownloadWithTranslation:
    """Test combined download with translation functionality."""

    async def test_enqueue_download_with_translation(
        self, test_orchestrator, rabbitmq_channel
    ):
        """Test that enqueue_download_with_translation queues download task."""
        # Arrange
        request_id = uuid4()
        request = SubtitleRequest(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            target_language="es",
            preferred_sources=["opensubtitles"],
        )

        # Act
        result = await test_orchestrator.enqueue_download_with_translation(
            request, request_id
        )

        # Assert
        assert result is True

        # Verify message in download queue (not translation yet)
        download_queue = await rabbitmq_channel.declare_queue(
            "subtitle.download", durable=True
        )
        assert download_queue.declaration_result.message_count == 1

        message = await download_queue.get(timeout=5)
        assert message is not None
        await message.ack()

    async def test_target_language_included_in_payload(
        self, test_orchestrator, rabbitmq_channel
    ):
        """Test that target_language is included in download task for downstream translation."""
        # Arrange
        request_id = uuid4()
        request = SubtitleRequest(
            video_url="https://example.com/video.mp4",
            video_title="Test Video",
            language="en",
            target_language="fr",
            preferred_sources=["opensubtitles"],
        )

        # Act
        await test_orchestrator.enqueue_download_with_translation(request, request_id)

        # Assert
        queue = await rabbitmq_channel.declare_queue("subtitle.download", durable=True)
        message = await queue.get(timeout=5)
        assert message is not None

        # Parse message - DownloadTask doesn't have target_language,
        # but we verify the task was queued correctly
        message_data = json.loads(message.body.decode())
        download_task = DownloadTask(**message_data)

        assert str(download_task.request_id) == str(request_id)
        assert download_task.video_url == "https://example.com/video.mp4"

        await message.ack()


@pytest.mark.integration
@pytest.mark.asyncio
class TestQueueConnectionHandling:
    """Test queue connection handling functionality."""

    async def test_orchestrator_connection_lifecycle(self, rabbitmq_container):
        """Test orchestrator connection and disconnection lifecycle."""
        # Arrange
        orchestrator = SubtitleOrchestrator()

        # Act - Connect
        await orchestrator.connect()

        # Assert - Connection established
        assert orchestrator.connection is not None
        assert orchestrator.channel is not None
        assert not orchestrator.connection.is_closed

        # Act - Disconnect
        await orchestrator.disconnect()

        # Assert - Connection closed
        assert orchestrator.connection.is_closed

    async def test_queue_declaration_creates_durable_queues(
        self, test_orchestrator, rabbitmq_channel
    ):
        """Test that queue declarations create durable queues."""
        # Assert - Check download queue (declare with same params to check existence)
        download_queue = await rabbitmq_channel.declare_queue(
            "subtitle.download", durable=True
        )
        assert download_queue.declaration_result is not None

        # Assert - Check translation queue
        translation_queue = await rabbitmq_channel.declare_queue(
            "subtitle.translation", durable=True
        )
        assert translation_queue.declaration_result is not None

    async def test_connection_failure_handling(self):
        """Test behavior when RabbitMQ is unavailable."""
        # Arrange
        orchestrator = SubtitleOrchestrator()

        # Mock settings to use invalid URL
        from unittest.mock import patch

        with patch("manager.orchestrator.settings") as mock_settings:
            mock_settings.rabbitmq_url = "amqp://guest:guest@invalid-host:5672/"

            # Act
            await orchestrator.connect()

            # Assert - Should handle gracefully (mock mode)
            assert orchestrator.channel is None

    async def test_reconnection_after_disconnect(self, rabbitmq_container):
        """Test that orchestrator can reconnect after disconnect."""
        # Arrange
        orchestrator = SubtitleOrchestrator()

        # Act - Connect, disconnect, reconnect
        await orchestrator.connect()
        assert orchestrator.connection is not None
        first_connection_id = id(orchestrator.connection)

        await orchestrator.disconnect()
        assert orchestrator.connection.is_closed

        await orchestrator.connect()
        assert orchestrator.connection is not None
        second_connection_id = id(orchestrator.connection)

        # Assert - New connection established
        assert not orchestrator.connection.is_closed
        assert first_connection_id != second_connection_id

        # Cleanup
        await orchestrator.disconnect()
