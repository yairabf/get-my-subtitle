# Integration Tests for Queue Publishing

This directory contains integration tests for RabbitMQ queue publishing functionality. These tests validate the full flow of message publishing to RabbitMQ using a real RabbitMQ instance.

## Overview

The integration tests cover:

1. **Queue Publishing** (`test_queue_publishing.py`)
   - SubtitleOrchestrator download queue operations
   - SubtitleOrchestrator translation queue operations
   - Queue connection handling and lifecycle
   - Message persistence and durability

2. **Event Publishing** (`test_event_publishing.py`)
   - EventPublisher topic exchange operations
   - Event routing and subscription patterns
   - Wildcard routing patterns
   - Multiple consumer scenarios

3. **End-to-End Flows** (`test_full_publishing_flow.py`)
   - Complete download request workflows
   - Complete translation request workflows
   - Error scenarios and edge cases
   - Concurrent publishing

## Prerequisites

### Required Services

- **Docker**: For running RabbitMQ container
- **docker-compose**: For managing services
- **RabbitMQ**: Provided via docker-compose

### Installation

Ensure you have the required Python packages:

```bash
pip install -r requirements.txt
```

## Running Integration Tests

### Option 1: Using the Helper Script (Recommended)

The helper script automatically starts RabbitMQ, runs the tests, and reports results:

```bash
./scripts/run_integration_tests.sh
```

### Option 2: Manual Execution

1. **Start RabbitMQ**:
   ```bash
   docker-compose up -d rabbitmq
   ```

2. **Wait for RabbitMQ to be ready**:
   ```bash
   # Wait until this command succeeds
   docker exec get-my-subtitle-rabbitmq-1 rabbitmq-diagnostics ping
   ```

3. **Run the integration tests**:
   ```bash
   # Run all integration tests
   pytest tests/integration/ -v -m integration

   # Run specific test file
   pytest tests/integration/test_queue_publishing.py -v

   # Run specific test class
   pytest tests/integration/test_queue_publishing.py::TestDownloadQueuePublishing -v

   # Run specific test
   pytest tests/integration/test_queue_publishing.py::TestDownloadQueuePublishing::test_enqueue_download_task_publishes_to_queue -v
   ```

4. **Stop RabbitMQ** (optional):
   ```bash
   docker-compose down rabbitmq
   ```

### Option 3: Run with Coverage

```bash
pytest tests/integration/ -v -m integration --cov=common --cov=manager --cov-report=html
```

## Test Organization

### Fixtures (`conftest.py`)

The integration tests use several fixtures to manage RabbitMQ connections and state:

- `rabbitmq_container`: Manages RabbitMQ Docker container lifecycle
- `rabbitmq_connection`: Provides RabbitMQ connection for tests
- `rabbitmq_channel`: Provides RabbitMQ channel for tests
- `clean_queues`: Purges queues before/after tests for isolation
- `clean_exchange`: Cleans topic exchange before/after tests
- `mock_redis_client`: Mocks Redis to isolate RabbitMQ testing
- `test_orchestrator`: Provides configured SubtitleOrchestrator instance
- `test_event_publisher`: Provides configured EventPublisher instance

### Test Files

#### `test_queue_publishing.py`

Tests for SubtitleOrchestrator queue operations:

- **TestDownloadQueuePublishing**: Download queue functionality
  - Message publishing to `subtitle.download` queue
  - Message format validation (DownloadTask schema)
  - Message persistence and routing
  - FIFO ordering

- **TestTranslationQueuePublishing**: Translation queue functionality
  - Message publishing to `subtitle.translation` queue
  - Message format validation (TranslationTask schema)
  - Message persistence and routing
  - FIFO ordering

- **TestCombinedDownloadWithTranslation**: Combined workflows
  - Download with translation queuing
  - Target language handling

- **TestQueueConnectionHandling**: Connection management
  - Connection lifecycle (connect/disconnect)
  - Queue durability
  - Connection failure handling
  - Reconnection logic

#### `test_event_publishing.py`

Tests for EventPublisher topic exchange operations:

- **TestTopicExchangePublishing**: Basic event publishing
  - Event publishing to `subtitle.events` exchange
  - Routing key validation
  - Event message format (SubtitleEvent schema)
  - Message persistence
  - All event types

- **TestEventSubscription**: Event consumption patterns
  - Specific routing key subscriptions
  - Wildcard routing patterns (`subtitle.*`, `subtitle.#`)
  - Multiple consumers (fanout behavior)

- **TestEventPublisherConnectionHandling**: Connection management
  - Connection lifecycle
  - Exchange type verification (TOPIC, durable)
  - Connection failure handling
  - Mock mode behavior

#### `test_full_publishing_flow.py`

End-to-end workflow tests:

- **TestDownloadRequestPublishingFlow**: Complete download workflows
  - Task and event publishing together
  - Task consumption by workers
  - Event subscription and processing

- **TestTranslationRequestPublishingFlow**: Complete translation workflows
  - Task and event publishing together
  - Task consumption by workers
  - Event subscription and processing

- **TestPublishingErrorScenarios**: Error handling
  - Invalid message formats
  - Non-existent queues (auto-creation)
  - Channel closure during publish
  - Concurrent publishing
  - Event publishing failures

## Test Strategy

### Isolation

Each test is isolated using:
- Unique request IDs (UUID) to prevent conflicts
- Queue purging before/after tests
- Exchange cleanup between tests
- Mocked Redis client to isolate RabbitMQ behavior

### Validation

Tests validate:
- **Message Serialization**: JSON format compliance
- **Schema Compliance**: DownloadTask, TranslationTask, SubtitleEvent schemas
- **Routing**: Correct routing keys and exchange bindings
- **Persistence**: Messages are durable and persistent
- **Queue Properties**: Queues and exchanges are properly configured

### Message Consumption Pattern

Tests use a consistent pattern:
1. Publish message/event
2. Create test consumer/queue
3. Consume message
4. Validate message content
5. Acknowledge message
6. Verify queue state

## Troubleshooting

### RabbitMQ Not Starting

If RabbitMQ fails to start:

```bash
# Check RabbitMQ logs
docker-compose logs rabbitmq

# Restart RabbitMQ
docker-compose restart rabbitmq

# Or remove and recreate
docker-compose down rabbitmq
docker-compose up -d rabbitmq
```

### Connection Refused Errors

If you see connection refused errors:

1. Verify RabbitMQ is running:
   ```bash
   docker ps | grep rabbitmq
   ```

2. Check RabbitMQ health:
   ```bash
   docker exec get-my-subtitle-rabbitmq-1 rabbitmq-diagnostics ping
   ```

3. Verify port mapping:
   ```bash
   docker port get-my-subtitle-rabbitmq-1
   # Should show: 5672/tcp -> 0.0.0.0:5672
   ```

### Test Timeout Errors

If tests timeout waiting for messages:

1. Check if RabbitMQ is healthy
2. Verify queues exist: Access RabbitMQ management UI at http://localhost:15672 (guest/guest)
3. Check for queue purging issues
4. Increase timeout values in tests if needed

### Message Count Mismatches

If message counts don't match expectations:

1. Ensure `clean_queues` fixture is being used
2. Check for messages from previous test runs
3. Manually purge queues via RabbitMQ management UI
4. Verify test isolation

## Configuration

### RabbitMQ Settings

Default RabbitMQ configuration (from `docker-compose.yml`):
- **Host**: localhost
- **Port**: 5672
- **Management UI**: http://localhost:15672
- **Credentials**: guest/guest
- **URL**: amqp://guest:guest@localhost:5672/

### Test Settings

Configuration is in `conftest.py`:
- Queue names: `subtitle.download`, `subtitle.translation`
- Exchange name: `subtitle.events`
- Exchange type: TOPIC
- Durability: All queues and exchanges are durable

## Best Practices

1. **Always use fixtures**: Use provided fixtures for connections and state management
2. **Clean state**: Rely on `clean_queues` and `clean_exchange` fixtures
3. **Unique identifiers**: Use `uuid4()` for request IDs
4. **Explicit acknowledgment**: Always acknowledge messages after consumption
5. **Timeout handling**: Use reasonable timeouts (5 seconds default)
6. **Async patterns**: Use proper async/await patterns with asyncio
7. **Error validation**: Test both success and failure scenarios

## CI/CD Integration

To integrate these tests into CI/CD:

```yaml
# Example GitHub Actions workflow
- name: Start RabbitMQ
  run: docker-compose up -d rabbitmq

- name: Wait for RabbitMQ
  run: |
    timeout 30 bash -c 'until docker exec get-my-subtitle-rabbitmq-1 rabbitmq-diagnostics ping; do sleep 1; done'

- name: Run Integration Tests
  run: pytest tests/integration/ -v -m integration --cov=common --cov=manager

- name: Cleanup
  if: always()
  run: docker-compose down
```

## Coverage

Integration tests provide coverage for:
- `manager/orchestrator.py`: SubtitleOrchestrator class
- `common/event_publisher.py`: EventPublisher class
- `common/schemas.py`: Message schemas (DownloadTask, TranslationTask, SubtitleEvent)

View coverage report:
```bash
pytest tests/integration/ --cov=common --cov=manager --cov-report=html
open htmlcov/index.html
```

## Contributing

When adding new integration tests:

1. Follow the existing test structure
2. Use descriptive test names
3. Add docstrings explaining what is tested
4. Ensure proper cleanup (use fixtures)
5. Test both success and error paths
6. Update this README if adding new test categories

## Resources

- [aio-pika Documentation](https://aio-pika.readthedocs.io/)
- [RabbitMQ Documentation](https://www.rabbitmq.com/documentation.html)
- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)

