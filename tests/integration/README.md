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

- **Docker**: For running RabbitMQ and Redis containers
- **docker-compose**: For managing services (automatically handled by pytest-docker)
- **pytest-docker**: Automatically manages container lifecycle

### Installation

Ensure you have the required Python packages:

```bash
pip install -r requirements.txt
```

This will install `pytest-docker` which automatically manages Docker Compose containers for tests.

## Docker Compose Files Overview

This project uses three different Docker Compose files for different purposes:

### 1. `docker-compose.yml` (Main/Production)

**Location**: Root directory  
**Purpose**: Full application stack for development/production

**Services**: RabbitMQ, Redis, Manager, Downloader, Translator, Consumer, Scanner

**When to use**:
- Local development with all services
- Production-like testing
- Manual testing of the complete system

**Usage**:
```bash
make up              # Start all services
make down            # Stop all services
docker-compose up    # Direct usage
```

**Characteristics**:
- Uses `.env` file for configuration
- Slower health checks (10s intervals, 30s start period)
- All application services included
- Production-like environment

### 2. `docker-compose.integration.yml` (Full Integration Test Environment)

**Location**: Root directory  
**Purpose**: Complete environment for end-to-end integration tests

**Services**: RabbitMQ, Redis, Manager, Downloader, Translator, Scanner

**When to use**:
- Full end-to-end integration tests with all application services
- Testing complete workflows with real services
- Debugging integration issues with full stack

**Usage**:
```bash
make test-integration-full    # Start environment, run tests, cleanup
make test-integration-up       # Start environment only
make test-integration-down     # Stop environment
docker-compose -f docker-compose.integration.yml up -d
```

**Characteristics**:
- Fast health checks (5s intervals, 10-15s start periods)
- Explicit `integration-test-network`
- Test-specific environment variables
- Scanner auto-scanning disabled
- Test media directory mounted

### 3. `tests/integration/docker-compose.yml` (pytest-docker Minimal)

**Location**: `tests/integration/` directory  
**Purpose**: Minimal setup for pytest-docker (infrastructure only)

**Services**: RabbitMQ, Redis only (no application services)

**When to use**:
- **Default for integration tests** - automatically used by pytest-docker
- Unit/integration tests that need real RabbitMQ/Redis but run test code locally
- Fast test execution without starting full application stack
- CI/CD pipelines

**Usage**:
```bash
# Automatically used by pytest-docker - no manual setup needed
pytest tests/integration/ -v -m integration
make test-integration
```

**Characteristics**:
- Minimal: only infrastructure services
- Automatically managed by pytest-docker
- Fast health checks (5s intervals, 10s start period)
- Tests run outside containers (in your local Python environment)
- Automatic container lifecycle management

### Quick Decision Guide

| Scenario | Use This File | Command |
|----------|---------------|---------|
| Local development | `docker-compose.yml` | `make up` |
| Full E2E integration tests | `docker-compose.integration.yml` | `make test-integration-full` |
| Unit/integration tests (default) | `tests/integration/docker-compose.yml` | `pytest tests/integration/` |
| CI/CD pipelines | `tests/integration/docker-compose.yml` | `pytest tests/integration/` |
| Debugging with full stack | `docker-compose.integration.yml` | `make test-integration-up` |

**Note**: For most integration testing, you don't need to choose - just run `pytest tests/integration/` and pytest-docker will automatically use `tests/integration/docker-compose.yml`.

## Running Integration Tests

### Simple Execution (Recommended)

Integration tests now automatically manage Docker containers using `pytest-docker`. Simply run:

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

**No manual Docker setup required!** The `pytest-docker` plugin automatically:
- Starts RabbitMQ and Redis containers before tests
- Waits for services to be healthy
- Sets up environment variables with correct connection URLs
- Cleans up containers after tests complete

### Using Makefile Targets

You can also use the Makefile targets:

```bash
# Run integration tests (containers managed automatically)
make test-integration

# Run with full Docker environment (for debugging)
make test-integration-full
```

### Option 3: Run with Coverage

```bash
pytest tests/integration/ -v -m integration --cov=common --cov=manager --cov-report=html
```

## Test Organization

### Fixtures (`conftest.py`)

The integration tests use `pytest-docker` to automatically manage Docker containers and provide fixtures:

**Docker Management (pytest-docker)**:
- `docker_compose_file`: Specifies the Docker Compose file for tests
- `docker_services`: Manages container lifecycle (automatic start/stop)
- `rabbitmq_service`: Waits for RabbitMQ to be ready and returns connection URL
- `redis_service`: Waits for Redis to be ready and returns connection URL

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
- `setup_environment_variables`: Automatically sets RABBITMQ_URL and REDIS_URL from Docker containers

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

### Containers Not Starting

If containers fail to start, pytest-docker will show error messages. Common issues:

1. **Port conflicts**: If ports 5672 or 6379 are already in use:
   ```bash
   # Check what's using the ports
   lsof -i :5672  # RabbitMQ
   lsof -i :6379  # Redis
   
   # Stop conflicting services or modify docker-compose.yml to use different ports
   ```

2. **Docker not running**: Ensure Docker is running:
   ```bash
   docker ps
   ```

3. **Insufficient resources**: Ensure Docker has enough memory/CPU allocated

### Connection Refused Errors

If you see connection refused errors:

1. Check pytest-docker output for container startup issues
2. Verify containers are running:
   ```bash
   docker ps | grep -E "rabbitmq|redis"
   ```
3. Check container logs:
   ```bash
   docker-compose -f tests/integration/docker-compose.yml logs
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

### Docker Compose Configuration

The integration tests use `tests/integration/docker-compose.yml` (see [Docker Compose Files Overview](#docker-compose-files-overview) for details on all three compose files). This minimal compose file defines:
- **RabbitMQ**: Port 5672 (AMQP), 15672 (Management UI)
- **Redis**: Port 6379
- **Credentials**: guest/guest (RabbitMQ)

**Note**: pytest-docker automatically maps ports and provides connection URLs via fixtures. Tests should use the `rabbitmq_service` and `redis_service` fixtures rather than hardcoded URLs.

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

Integration tests work seamlessly in CI/CD environments. pytest-docker handles all container management:

```yaml
# Example GitHub Actions workflow
- name: Run Integration Tests
  run: pytest tests/integration/ -v -m integration --cov=common --cov=manager
```

**No manual container setup needed!** pytest-docker automatically:
- Starts containers before tests
- Waits for services to be healthy
- Cleans up containers after tests (even on failure)

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

