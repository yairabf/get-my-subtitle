---
epic: testing-qa
task: CU-86ev9n27f_Integration-tests-with-Docker-Compose-RabbitMQ-Redis
created: 2025-01-XX
---

# Integration Tests with Docker Compose (RabbitMQ + Redis) - Implementation Plan

## Overview

This plan implements integration tests to verify system interactions between services using Docker Compose with RabbitMQ and Redis containers. The tests will validate real service interactions, message queue operations, and event publishing flows.

## Objectives

1. Set up Docker Compose configuration for RabbitMQ and Redis services
2. Create pytest fixtures for managing Docker containers during tests
3. Implement integration tests for queue publishing operations
4. Implement integration tests for event publishing operations
5. Implement end-to-end workflow tests
6. Ensure tests work in both local development and CI environments
7. Create comprehensive documentation

## Architecture

### Services Required

- **RabbitMQ**: Message broker for queue and event operations
- **Redis**: In-memory data store for job state and caching

### Test Structure

```
tests/integration/
├── __init__.py
├── conftest.py              # Pytest fixtures for Docker services
├── test_queue_publishing.py # Queue publishing tests
├── test_event_publishing.py # Event publishing tests
├── test_full_publishing_flow.py # End-to-end tests
└── README.md                # Test documentation
```

## Implementation Tasks

### 1. Docker Compose Configuration

**File**: `tests/integration/docker-compose.yml`

- Define RabbitMQ service with management plugin
- Define Redis service with persistence
- Configure health checks for both services
- Set up proper networking and port mappings
- Configure environment variables

**Requirements**:
- RabbitMQ on port 5672 (AMQP) and 15672 (Management UI)
- Redis on port 6379
- Health checks to ensure services are ready
- Proper cleanup on test completion

### 2. Pytest Fixtures (`conftest.py`)

**Service Management Fixtures**:
- `rabbitmq_service`: Ensures RabbitMQ is up and responsive
- `redis_service`: Ensures Redis is up and responsive
- `setup_environment_variables`: Sets RABBITMQ_URL and REDIS_URL

**RabbitMQ Fixtures**:
- `rabbitmq_container`: Container connection info
- `rabbitmq_connection`: Active RabbitMQ connection
- `rabbitmq_channel`: RabbitMQ channel for operations
- `clean_queues`: Purges queues before/after tests
- `clean_exchange`: Cleans topic exchange before/after tests

**Redis Fixtures**:
- `fake_redis_client`: Fake Redis client using fakeredis
- `fake_redis_job_client`: RedisJobClient with fakeredis
- `mock_redis_client`: Simple mock for backward compatibility

**Application Fixtures**:
- `test_orchestrator`: SubtitleOrchestrator instance for testing
- `test_event_publisher`: EventPublisher instance for testing

**Requirements**:
- Environment-aware (CI vs local)
- Automatic service health checks
- Proper cleanup and isolation
- Support for both real and fake Redis

### 3. Queue Publishing Tests (`test_queue_publishing.py`)

**Test Classes**:

1. **TestDownloadQueuePublishing**
   - Test enqueue download task publishes to queue
   - Test download task message format
   - Test download task persistence
   - Test download task routing key
   - Test multiple download tasks queued in order

2. **TestTranslationQueuePublishing**
   - Test enqueue translation task publishes to queue
   - Test translation task message format
   - Test translation task persistence
   - Test translation task routing key
   - Test multiple translation tasks queued in order

3. **TestCombinedDownloadWithTranslation**
   - Test enqueue download with translation
   - Test target language included in payload

4. **TestQueueConnectionHandling**
   - Test orchestrator connection lifecycle
   - Test queue declaration creates durable queues
   - Test connection failure handling (mock mode)
   - Test reconnection after disconnect

**Requirements**:
- Verify message format and content
- Verify message persistence
- Verify queue operations
- Test error scenarios
- Test connection handling

### 4. Event Publishing Tests (`test_event_publishing.py`)

**Test Classes**:

1. **TestTopicExchangePublishing**
   - Test publish event to topic exchange
   - Test event routing keys match event types
   - Test event message format
   - Test event persistence
   - Test multiple event types published

2. **TestEventSubscription**
   - Test consumer receives events by routing key
   - Test wildcard routing patterns
   - Test multiple consumers receive same event

3. **TestEventPublisherConnectionHandling**
   - Test event publisher connection lifecycle
   - Test exchange declaration creates topic exchange
   - Test connection failure returns false (mock mode)
   - Test mock mode when disconnected

**Requirements**:
- Verify event format and content
- Verify routing key patterns
- Verify topic exchange behavior
- Test subscription patterns
- Test connection handling

### 5. End-to-End Flow Tests (`test_full_publishing_flow.py`)

**Test Classes**:

1. **TestDownloadRequestPublishingFlow**
   - Test download request publishes task and event
   - Test download task can be consumed
   - Test download event can be subscribed

2. **TestTranslationRequestPublishingFlow**
   - Test translation request publishes task and event
   - Test translation task can be consumed
   - Test translation event can be subscribed

3. **TestPublishingErrorScenarios**
   - Test publish with invalid message format
   - Test publish to non-existent queue
   - Test channel closed during publish
   - Test concurrent publishing to same queue
   - Test event publishing failure doesn't block task

**Requirements**:
- Verify complete workflows
- Verify message consumption
- Test error scenarios
- Test concurrent operations

### 6. Configuration Updates

**pytest.ini**:
- Add `integration` marker
- Add `skip_services` marker for tests that don't need real services
- Configure test discovery

**CI/CD Integration**:
- Update GitHub Actions workflow
- Add integration test job
- Configure service containers in CI
- Set environment variables

### 7. Documentation

**Files to Create**:
- `tests/integration/README.md`: Quick reference guide
- `docs/INTEGRATION_TESTING.md`: Comprehensive documentation

**Content**:
- Overview and architecture
- Prerequisites and setup
- Running tests (local and CI)
- Test organization
- Troubleshooting guide
- Best practices
- Docker Compose file comparison

## Technical Decisions

### Service Management

**Initial Approach**: Use `pytest-docker` plugin
- **Issue**: Dependency conflict with pytest 8.3.4
- **Solution**: Custom environment-aware fixtures that work with:
  - GitHub Actions services (CI)
  - Local Docker Compose
  - Manual service setup

### Redis Testing Strategy

**Approach**: Use fakeredis for most integration tests
- Provides realistic Redis behavior
- Keeps tests focused on RabbitMQ integration
- Allows tests to run without real Redis when needed

### Connection Failure Testing

**Approach**: Mock `aio_pika.connect_robust` to raise exceptions
- Tests verify mock mode behavior
- Uses `@pytest.mark.skip_services` to skip service requirements
- Ensures graceful degradation

## Success Criteria

- ✅ All integration tests pass in CI
- ✅ Tests work in local development environment
- ✅ Proper test isolation with fixtures
- ✅ Comprehensive coverage of queue and event operations
- ✅ Error scenarios tested
- ✅ Documentation complete
- ✅ No linting errors
- ✅ CI/CD integration working

## Dependencies

- `pytest==8.3.4`
- `pytest-asyncio==0.24.0`
- `pytest-cov==6.0.0`
- `aio-pika==9.3.1`
- `redis==5.2.0`
- `fakeredis[aioredis]==2.25.1`
- Docker and Docker Compose

## Notes

- Tests should be fast and isolated
- Use health checks to ensure services are ready
- Clean up resources after tests
- Support both CI and local environments
- Handle connection failures gracefully

