# Integration Tests

This directory contains integration tests for the subtitle processing system. These tests validate interactions between services using real RabbitMQ and Redis instances managed by pytest-docker.

> **📖 For comprehensive documentation**: See [`docs/INTEGRATION_TESTING.md`](../../docs/INTEGRATION_TESTING.md) for architecture, service details, and troubleshooting.

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

## Quick Start

```bash
# Run all integration tests (containers managed automatically)
pytest tests/integration/ -v -m integration

# Or use Makefile
make test-integration
```

**Setup**:
- **CI**: Services provided automatically by GitHub Actions
- **Local**: Start services with `docker-compose up -d rabbitmq redis` or `make up-infra`

> **📖 See [docs/INTEGRATION_TESTING.md](../../docs/INTEGRATION_TESTING.md) for prerequisites, installation, and detailed usage.**

## Docker Compose Files

This project uses three Docker Compose files. **For local integration tests, use `tests/integration/docker-compose.yml`** (infrastructure only). In CI, services are provided automatically by GitHub Actions.

| File | Purpose | When to Use |
|------|---------|-------------|
| `docker-compose.yml` | Full application stack | `make up` - Local development |
| `docker-compose.integration.yml` | Full E2E test environment | `make test-integration-full` - Full stack testing |
| `tests/integration/docker-compose.yml` | **Minimal (local dev)** | `docker-compose -f tests/integration/docker-compose.yml up -d` |

> **📖 See [docs/INTEGRATION_TESTING.md](../../docs/INTEGRATION_TESTING.md) for detailed comparison and when to use each.**

## Running Tests

```bash
# All integration tests
pytest tests/integration/ -v -m integration

# Specific test file
pytest tests/integration/test_queue_publishing.py -v

# Specific test
pytest tests/integration/test_queue_publishing.py::TestDownloadQueuePublishing::test_enqueue_download_task_publishes_to_queue -v

# With coverage
pytest tests/integration/ -v -m integration --cov=common --cov=manager --cov-report=html

# Using Makefile
make test-integration              # pytest-docker (default)
make test-integration-full         # Full Docker stack
```

## Test Organization

### Fixtures (`conftest.py`)

The integration tests use fixtures that automatically detect the environment (CI vs local):

**Service Fixtures**:
- `rabbitmq_service`: Detects CI/local, waits for RabbitMQ to be ready, returns connection URL
- `redis_service`: Detects CI/local, waits for Redis to be ready, returns connection URL
- `setup_environment_variables`: Automatically sets RABBITMQ_URL and REDIS_URL from service fixtures

**RabbitMQ Fixtures**:
- `rabbitmq_container`: Backward compatibility fixture (returns connection info dict)
- `rabbitmq_connection`: Provides RabbitMQ connection for tests
- `rabbitmq_channel`: Provides RabbitMQ channel for tests
- `clean_queues`: Purges queues before/after tests for isolation
- `clean_exchange`: Cleans topic exchange before/after tests

**Redis Fixtures**:
- `fake_redis_client`: Fake Redis client using fakeredis (for isolated testing)
- `fake_redis_job_client`: RedisJobClient instance using fakeredis
- `mock_redis_client`: Simple mock Redis client for backward compatibility

**Application Fixtures**:
- `test_orchestrator`: Provides configured SubtitleOrchestrator instance
- `test_event_publisher`: Provides configured EventPublisher instance
- `setup_environment_variables`: Automatically sets RABBITMQ_URL and REDIS_URL from service fixtures

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

**Quick fixes:**
- Port conflicts: `lsof -i :5672` or `lsof -i :6379`
- Docker not running: `docker ps`
- View logs: `docker-compose -f tests/integration/docker-compose.yml logs`

> **📖 See [docs/INTEGRATION_TESTING.md](../../docs/INTEGRATION_TESTING.md) for comprehensive troubleshooting guide.**

## Configuration

**Test Settings** (in `conftest.py`):
- Queues: `subtitle.download`, `subtitle.translation`
- Exchange: `subtitle.events` (TOPIC, durable)
- Credentials: guest/guest (RabbitMQ)

**Note**: In CI, services are on localhost. Locally, use `rabbitmq_service` and `redis_service` fixtures which auto-detect the environment.

> **📖 See [docs/INTEGRATION_TESTING.md](../../docs/INTEGRATION_TESTING.md) for environment configuration details.**

## Best Practices

1. **Always use fixtures**: Use provided fixtures for connections and state management
2. **Clean state**: Rely on `clean_queues` and `clean_exchange` fixtures
3. **Unique identifiers**: Use `uuid4()` for request IDs
4. **Explicit acknowledgment**: Always acknowledge messages after consumption
5. **Timeout handling**: Use reasonable timeouts (5 seconds default)
6. **Async patterns**: Use proper async/await patterns with asyncio
7. **Error validation**: Test both success and failure scenarios

## CI/CD

```yaml
- name: Run Integration Tests
  run: pytest tests/integration/ -v -m integration --cov=common --cov=manager
```

> **📖 See [docs/INTEGRATION_TESTING.md](../../docs/INTEGRATION_TESTING.md) for CI/CD integration details.**

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

