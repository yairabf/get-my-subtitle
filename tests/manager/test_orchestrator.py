"""Unit tests for SubtitleOrchestrator combining Redis and RabbitMQ mocks."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import aio_pika
import pytest

from common.schemas import (
    DownloadTask,
    EventType,
    SubtitleRequest,
    SubtitleStatus,
    TranslationTask,
)
from manager.orchestrator import SubtitleOrchestrator


@pytest.mark.unit
@pytest.mark.asyncio
class TestOrchestratorConnection:
    """Test SubtitleOrchestrator RabbitMQ connection and queue declaration."""

    async def test_connect_establishes_rabbitmq_connection(
        self, mock_rabbitmq_connection, mock_rabbitmq_channel
    ):
        """Test that connect establishes RabbitMQ connection."""
        orchestrator = SubtitleOrchestrator()

        with patch(
            "manager.orchestrator.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )

            with patch("manager.orchestrator.event_publisher") as mock_publisher:
                mock_publisher.connect = AsyncMock()

                await orchestrator.connect()

                assert orchestrator.connection is not None
                assert orchestrator.channel is not None

    async def test_connect_declares_download_and_translation_queues(
        self, mock_rabbitmq_connection, mock_rabbitmq_channel
    ):
        """Test that connect declares both download and translation queues."""
        orchestrator = SubtitleOrchestrator()

        with patch(
            "manager.orchestrator.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )

            with patch("manager.orchestrator.event_publisher") as mock_publisher:
                mock_publisher.connect = AsyncMock()

                await orchestrator.connect()

                # Verify queue declarations
                assert mock_rabbitmq_channel.declare_queue.call_count == 2

                # Check that download and translation queues were declared
                call_args_list = mock_rabbitmq_channel.declare_queue.call_args_list
                queue_names = [call[0][0] for call in call_args_list]
                assert "subtitle.download" in queue_names
                assert "subtitle.translation" in queue_names

    async def test_connect_declares_durable_queues(
        self, mock_rabbitmq_connection, mock_rabbitmq_channel
    ):
        """Test that queues are declared as durable."""
        orchestrator = SubtitleOrchestrator()

        with patch(
            "manager.orchestrator.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )

            with patch("manager.orchestrator.event_publisher") as mock_publisher:
                mock_publisher.connect = AsyncMock()

                await orchestrator.connect()

                # Verify durable flag
                call_args_list = mock_rabbitmq_channel.declare_queue.call_args_list
                for call in call_args_list:
                    assert call[1]["durable"] is True

    async def test_disconnect_closes_connections(
        self, mock_rabbitmq_connection, mock_rabbitmq_channel
    ):
        """Test that disconnect closes RabbitMQ and event publisher connections."""
        orchestrator = SubtitleOrchestrator()

        with patch(
            "manager.orchestrator.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )

            with patch("manager.orchestrator.event_publisher") as mock_publisher:
                mock_publisher.connect = AsyncMock()
                mock_publisher.disconnect = AsyncMock()

                await orchestrator.connect()
                await orchestrator.disconnect()

                mock_rabbitmq_connection.close.assert_called_once()
                mock_publisher.disconnect.assert_called_once()

    async def test_connect_handles_failure_gracefully(self):
        """Test that connect handles connection failures without raising exception."""
        orchestrator = SubtitleOrchestrator()

        with patch(
            "manager.orchestrator.aio_pika.connect_robust",
            side_effect=Exception("Connection failed"),
        ):
            # Should not raise exception
            await orchestrator.connect()

            # Should be in mock mode
            assert orchestrator.connection is None
            assert orchestrator.channel is None


@pytest.mark.unit
@pytest.mark.asyncio
class TestOrchestratorDownloadTaskQueuing:
    """Test SubtitleOrchestrator download task enqueuing with Redis/event integration."""

    async def test_enqueue_download_task_publishes_to_queue(
        self,
        mock_rabbitmq_connection,
        mock_rabbitmq_channel,
        sample_subtitle_request_obj,
    ):
        """Test that enqueue_download_task publishes message to download queue."""
        orchestrator = SubtitleOrchestrator()
        request_id = uuid4()

        with patch(
            "manager.orchestrator.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )

            with patch("manager.orchestrator.event_publisher") as mock_publisher:
                mock_publisher.connect = AsyncMock()
                mock_publisher.publish_event = AsyncMock(return_value=True)

                await orchestrator.connect()
                result = await orchestrator.enqueue_download_task(
                    sample_subtitle_request_obj, request_id
                )

                assert result is True
                mock_rabbitmq_channel.default_exchange.publish.assert_called_once()

    async def test_enqueue_download_task_creates_valid_download_task(
        self,
        mock_rabbitmq_connection,
        mock_rabbitmq_channel,
        sample_subtitle_request_obj,
    ):
        """Test that enqueue_download_task creates valid DownloadTask message."""
        orchestrator = SubtitleOrchestrator()
        request_id = uuid4()

        with patch(
            "manager.orchestrator.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )

            with patch("manager.orchestrator.event_publisher") as mock_publisher:
                mock_publisher.connect = AsyncMock()
                mock_publisher.publish_event = AsyncMock(return_value=True)

                await orchestrator.connect()
                await orchestrator.enqueue_download_task(
                    sample_subtitle_request_obj, request_id
                )

                # Verify message content
                call_args = mock_rabbitmq_channel.default_exchange.publish.call_args
                message = call_args[0][0]
                message_data = json.loads(message.body.decode())
                download_task = DownloadTask(**message_data)

                assert str(download_task.request_id) == str(request_id)
                assert download_task.video_url == sample_subtitle_request_obj.video_url
                assert download_task.language == sample_subtitle_request_obj.language

    async def test_enqueue_download_task_uses_correct_routing_key(
        self,
        mock_rabbitmq_connection,
        mock_rabbitmq_channel,
        sample_subtitle_request_obj,
    ):
        """Test that enqueue_download_task uses correct routing key."""
        orchestrator = SubtitleOrchestrator()
        request_id = uuid4()

        with patch(
            "manager.orchestrator.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )

            with patch("manager.orchestrator.event_publisher") as mock_publisher:
                mock_publisher.connect = AsyncMock()
                mock_publisher.publish_event = AsyncMock(return_value=True)

                await orchestrator.connect()
                await orchestrator.enqueue_download_task(
                    sample_subtitle_request_obj, request_id
                )

                # Verify routing key
                call_args = mock_rabbitmq_channel.default_exchange.publish.call_args
                assert call_args[1]["routing_key"] == "subtitle.download"

    async def test_enqueue_download_task_creates_persistent_message(
        self,
        mock_rabbitmq_connection,
        mock_rabbitmq_channel,
        sample_subtitle_request_obj,
    ):
        """Test that enqueue_download_task creates persistent message."""
        orchestrator = SubtitleOrchestrator()
        request_id = uuid4()

        with patch(
            "manager.orchestrator.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )

            with patch("manager.orchestrator.event_publisher") as mock_publisher:
                mock_publisher.connect = AsyncMock()
                mock_publisher.publish_event = AsyncMock(return_value=True)

                await orchestrator.connect()
                await orchestrator.enqueue_download_task(
                    sample_subtitle_request_obj, request_id
                )

                # Verify message persistence
                call_args = mock_rabbitmq_channel.default_exchange.publish.call_args
                message = call_args[0][0]
                assert message.delivery_mode == aio_pika.DeliveryMode.PERSISTENT

    async def test_enqueue_download_task_publishes_event(
        self,
        mock_rabbitmq_connection,
        mock_rabbitmq_channel,
        sample_subtitle_request_obj,
    ):
        """Test that enqueue_download_task publishes event."""
        orchestrator = SubtitleOrchestrator()
        request_id = uuid4()

        with patch(
            "manager.orchestrator.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )

            with patch("manager.orchestrator.event_publisher") as mock_publisher:
                mock_publisher.connect = AsyncMock()
                mock_publisher.publish_event = AsyncMock(return_value=True)

                await orchestrator.connect()
                await orchestrator.enqueue_download_task(
                    sample_subtitle_request_obj, request_id
                )

                # Verify event was published
                mock_publisher.publish_event.assert_called_once()
                event = mock_publisher.publish_event.call_args[0][0]
                assert event.event_type == EventType.SUBTITLE_DOWNLOAD_REQUESTED
                assert event.job_id == request_id

    async def test_enqueue_download_task_does_not_update_redis_directly(
        self,
        mock_rabbitmq_connection,
        mock_rabbitmq_channel,
        sample_subtitle_request_obj,
    ):
        """Test that enqueue_download_task does NOT update Redis directly (event-driven)."""
        orchestrator = SubtitleOrchestrator()
        request_id = uuid4()

        with patch(
            "manager.orchestrator.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )

            with patch("manager.orchestrator.event_publisher") as mock_publisher:
                mock_publisher.connect = AsyncMock()
                mock_publisher.publish_event = AsyncMock(return_value=True)

                # Patch redis_client at the common module level to verify it's not called
                with patch("common.redis_client.redis_client") as mock_redis:
                    mock_redis.update_phase = AsyncMock()
                    await orchestrator.connect()
                    await orchestrator.enqueue_download_task(
                        sample_subtitle_request_obj, request_id
                    )

                    # Verify NO direct Redis update (Consumer will handle it)
                    mock_redis.update_phase.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
class TestOrchestratorTranslationTaskQueuing:
    """Test SubtitleOrchestrator translation task enqueuing with Redis/event integration."""

    async def test_enqueue_translation_task_publishes_to_queue(
        self, mock_rabbitmq_connection, mock_rabbitmq_channel
    ):
        """Test that enqueue_translation_task publishes message to translation queue."""
        orchestrator = SubtitleOrchestrator()
        request_id = uuid4()

        with patch(
            "manager.orchestrator.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )

            with patch("manager.orchestrator.event_publisher") as mock_publisher:
                mock_publisher.connect = AsyncMock()
                mock_publisher.publish_event = AsyncMock(return_value=True)

                await orchestrator.connect()
                result = await orchestrator.enqueue_translation_task(
                    request_id,
                    "/path/to/subtitle.srt",
                    "en",
                    "es",
                )

                assert result is True
                mock_rabbitmq_channel.default_exchange.publish.assert_called_once()

    async def test_enqueue_translation_task_creates_valid_translation_task(
        self, mock_rabbitmq_connection, mock_rabbitmq_channel
    ):
        """Test that enqueue_translation_task creates valid TranslationTask message."""
        orchestrator = SubtitleOrchestrator()
        request_id = uuid4()

        with patch(
            "manager.orchestrator.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )

            with patch("manager.orchestrator.event_publisher") as mock_publisher:
                mock_publisher.connect = AsyncMock()
                mock_publisher.publish_event = AsyncMock(return_value=True)

                await orchestrator.connect()
                await orchestrator.enqueue_translation_task(
                    request_id,
                    "/path/to/subtitle.srt",
                    "en",
                    "fr",
                )

                # Verify message content
                call_args = mock_rabbitmq_channel.default_exchange.publish.call_args
                message = call_args[0][0]
                message_data = json.loads(message.body.decode())
                translation_task = TranslationTask(**message_data)

                assert str(translation_task.request_id) == str(request_id)
                assert translation_task.subtitle_file_path == "/path/to/subtitle.srt"
                assert translation_task.source_language == "en"
                assert translation_task.target_language == "fr"

    async def test_enqueue_translation_task_uses_correct_routing_key(
        self, mock_rabbitmq_connection, mock_rabbitmq_channel
    ):
        """Test that enqueue_translation_task uses correct routing key."""
        orchestrator = SubtitleOrchestrator()
        request_id = uuid4()

        with patch(
            "manager.orchestrator.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )

            with patch("manager.orchestrator.event_publisher") as mock_publisher:
                mock_publisher.connect = AsyncMock()
                mock_publisher.publish_event = AsyncMock(return_value=True)

                await orchestrator.connect()
                await orchestrator.enqueue_translation_task(
                    request_id,
                    "/path/to/subtitle.srt",
                    "en",
                    "es",
                )

                # Verify routing key
                call_args = mock_rabbitmq_channel.default_exchange.publish.call_args
                assert call_args[1]["routing_key"] == "subtitle.translation"

    async def test_enqueue_translation_task_publishes_event(
        self, mock_rabbitmq_connection, mock_rabbitmq_channel
    ):
        """Test that enqueue_translation_task enqueues task to RabbitMQ."""
        orchestrator = SubtitleOrchestrator()
        request_id = uuid4()

        with patch(
            "manager.orchestrator.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )

            await orchestrator.connect()
            await orchestrator.enqueue_translation_task(
                request_id,
                "/path/to/subtitle.srt",
                "en",
                "es",
            )

            # Verify message was published to RabbitMQ translation queue
            mock_rabbitmq_channel.default_exchange.publish.assert_called_once()
            call_args = mock_rabbitmq_channel.default_exchange.publish.call_args
            assert call_args[1]["routing_key"] == "subtitle.translation"

            # Verify message body contains translation task
            message_body = call_args[0][0].body
            task_data = json.loads(message_body.decode())
            assert task_data["request_id"] == str(request_id)
            assert task_data["subtitle_file_path"] == "/path/to/subtitle.srt"
            assert task_data["source_language"] == "en"
            assert task_data["target_language"] == "es"

    async def test_enqueue_translation_task_does_not_update_redis_directly(
        self, mock_rabbitmq_connection, mock_rabbitmq_channel
    ):
        """Test that enqueue_translation_task does NOT update Redis directly (event-driven)."""
        orchestrator = SubtitleOrchestrator()
        request_id = uuid4()

        with patch(
            "manager.orchestrator.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )

            with patch("manager.orchestrator.event_publisher") as mock_publisher:
                mock_publisher.connect = AsyncMock()
                mock_publisher.publish_event = AsyncMock(return_value=True)

                # Patch redis_client at the common module level to verify it's not called
                with patch("common.redis_client.redis_client") as mock_redis:
                    mock_redis.update_phase = AsyncMock()
                    await orchestrator.connect()
                    await orchestrator.enqueue_translation_task(
                        request_id,
                        "/path/to/subtitle.srt",
                        "en",
                        "es",
                    )

                    # Verify NO direct Redis update (Consumer will handle it)
                    mock_redis.update_phase.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
class TestOrchestratorCombinedWorkflow:
    """Test SubtitleOrchestrator combined download+translation workflows."""

    async def test_enqueue_download_with_translation_calls_download_task(
        self,
        mock_rabbitmq_connection,
        mock_rabbitmq_channel,
        sample_subtitle_request_obj,
    ):
        """Test that enqueue_download_with_translation enqueues download task."""
        orchestrator = SubtitleOrchestrator()
        request_id = uuid4()

        with patch(
            "manager.orchestrator.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )

            with patch("manager.orchestrator.event_publisher") as mock_publisher:
                mock_publisher.connect = AsyncMock()
                mock_publisher.publish_event = AsyncMock(return_value=True)

                await orchestrator.connect()
                result = await orchestrator.enqueue_download_with_translation(
                    sample_subtitle_request_obj, request_id
                )

                assert result is True
                # Should publish to download queue
                mock_rabbitmq_channel.default_exchange.publish.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
class TestOrchestratorQueueStatus:
    """Test SubtitleOrchestrator queue status monitoring."""

    async def test_get_queue_status_returns_queue_sizes(
        self, mock_rabbitmq_connection, mock_rabbitmq_channel
    ):
        """Test that get_queue_status returns message counts for queues."""
        orchestrator = SubtitleOrchestrator()

        # Configure mock queues with message counts
        mock_download_queue = AsyncMock()
        mock_download_queue.declaration_result = MagicMock()
        mock_download_queue.declaration_result.message_count = 5

        mock_translation_queue = AsyncMock()
        mock_translation_queue.declaration_result = MagicMock()
        mock_translation_queue.declaration_result.message_count = 3

        async def mock_declare_queue(name, passive=False, durable=False):
            if name == "subtitle.download":
                return mock_download_queue
            elif name == "subtitle.translation":
                return mock_translation_queue
            return AsyncMock()

        with patch(
            "manager.orchestrator.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )
            mock_rabbitmq_channel.declare_queue = mock_declare_queue

            with patch("manager.orchestrator.event_publisher") as mock_publisher:
                mock_publisher.connect = AsyncMock()

                await orchestrator.connect()
                status = await orchestrator.get_queue_status()

                assert status["download_queue_size"] == 5
                assert status["translation_queue_size"] == 3


@pytest.mark.unit
@pytest.mark.asyncio
class TestOrchestratorMockMode:
    """Test SubtitleOrchestrator mock mode behavior when dependencies unavailable."""

    async def test_enqueue_download_task_in_mock_mode_returns_true(
        self, sample_subtitle_request_obj
    ):
        """Test that enqueue_download_task in mock mode returns True."""
        orchestrator = SubtitleOrchestrator()
        # Don't connect - stays in mock mode

        result = await orchestrator.enqueue_download_task(
            sample_subtitle_request_obj, uuid4()
        )

        assert result is True

    async def test_enqueue_translation_task_in_mock_mode_returns_true(self):
        """Test that enqueue_translation_task in mock mode returns True."""
        orchestrator = SubtitleOrchestrator()
        # Don't connect - stays in mock mode

        result = await orchestrator.enqueue_translation_task(
            uuid4(), "/path/to/subtitle.srt", "en", "es"
        )

        assert result is True

    async def test_get_queue_status_in_mock_mode_returns_zeros(self):
        """Test that get_queue_status in mock mode returns zero counts."""
        orchestrator = SubtitleOrchestrator()
        # Don't connect - stays in mock mode

        status = await orchestrator.get_queue_status()

        assert status["download_queue_size"] == 0
        assert status["translation_queue_size"] == 0


@pytest.mark.unit
@pytest.mark.asyncio
class TestOrchestratorErrorHandling:
    """Test SubtitleOrchestrator error scenarios and rollback."""

    async def test_enqueue_download_task_returns_false_on_error(
        self,
        mock_rabbitmq_connection,
        mock_rabbitmq_channel,
        sample_subtitle_request_obj,
    ):
        """Test that enqueue_download_task returns False when publishing fails."""
        orchestrator = SubtitleOrchestrator()
        request_id = uuid4()

        with patch(
            "manager.orchestrator.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )

            # Make publish raise an error
            mock_rabbitmq_channel.default_exchange.publish = AsyncMock(
                side_effect=Exception("Publish failed")
            )

            with patch("manager.orchestrator.event_publisher") as mock_publisher:
                mock_publisher.connect = AsyncMock()

                await orchestrator.connect()
                result = await orchestrator.enqueue_download_task(
                    sample_subtitle_request_obj, request_id
                )

                assert result is False

    async def test_enqueue_translation_task_returns_false_on_error(
        self, mock_rabbitmq_connection, mock_rabbitmq_channel
    ):
        """Test that enqueue_translation_task returns False when publishing fails."""
        orchestrator = SubtitleOrchestrator()
        request_id = uuid4()

        with patch(
            "manager.orchestrator.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )

            # Make publish raise an error
            mock_rabbitmq_channel.default_exchange.publish = AsyncMock(
                side_effect=Exception("Publish failed")
            )

            with patch("manager.orchestrator.event_publisher") as mock_publisher:
                mock_publisher.connect = AsyncMock()

                await orchestrator.connect()
                result = await orchestrator.enqueue_translation_task(
                    request_id, "/path/to/subtitle.srt", "en", "es"
                )

                assert result is False

    async def test_get_queue_status_handles_error_gracefully(
        self, mock_rabbitmq_connection, mock_rabbitmq_channel
    ):
        """Test that get_queue_status handles errors gracefully."""
        orchestrator = SubtitleOrchestrator()

        with patch(
            "manager.orchestrator.aio_pika.connect_robust",
            return_value=mock_rabbitmq_connection,
        ):
            mock_rabbitmq_connection.channel = AsyncMock(
                return_value=mock_rabbitmq_channel
            )

            # Make declare_queue raise an error
            mock_rabbitmq_channel.declare_queue = AsyncMock(
                side_effect=Exception("Queue error")
            )

            with patch("manager.orchestrator.event_publisher") as mock_publisher:
                mock_publisher.connect = AsyncMock()

                await orchestrator.connect()
                status = await orchestrator.get_queue_status()

                # Should return zeros on error
                assert status["download_queue_size"] == 0
                assert status["translation_queue_size"] == 0
