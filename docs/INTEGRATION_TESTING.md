# Integration Testing Environment

This document describes the dedicated integration testing environment for the subtitle processing system.

## Overview

The integration test environment provides a complete, isolated Docker-based setup for running end-to-end integration tests. It includes all services required for testing the full subtitle processing workflow.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                Integration Test Environment                  │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ RabbitMQ │    │  Redis   │    │ Manager  │              │
│  │  :5672   │    │  :6379   │    │  :8000   │              │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘              │
│       │               │               │                      │
│       └───────────────┴───────────────┘                      │
│                       │                                      │
│       ┌───────────────┼───────────────┐                      │
│       │               │               │                      │
│  ┌────▼────┐    ┌────▼────┐    ┌────▼────┐                 │
│  │ Scanner │    │Download │    │Translat │                 │
│  │  :8001  │    │  Worker │    │  Worker │                 │
│  └─────────┘    └─────────┘    └─────────┘                 │
│                                                               │
└─────────────────────────────────────────────────────────────┘
           ▲
           │
    ┌──────┴──────┐
    │  Test Suite │
    └─────────────┘
```

## Services

### Infrastructure Services
- **RabbitMQ**: Message broker for event-driven communication
  - Port: 5672 (AMQP), 15672 (Management UI)
  - Credentials: guest/guest
  
- **Redis**: In-memory data store for job state and caching
  - Port: 6379
  - Persistence: Enabled (appendonly)

### Application Services
- **Manager**: Orchestration service with REST API
  - Port: 8000
  - Consumes `SUBTITLE_REQUESTED` events
  - Enqueues download and translation tasks
  
- **Scanner**: Media detection and event publishing service
  - Port: 8001
  - Publishes `SUBTITLE_REQUESTED` events
  - Automatic scanning disabled in tests
  
- **Downloader**: Worker that downloads subtitles
  - Consumes from `subtitle.download` queue
  
- **Translator**: Worker that translates subtitles
  - Consumes from `subtitle.translate` queue

## Usage

### Quick Start - Run Full Integration Tests

Run all integration tests with automatic environment setup and teardown:

```bash
make test-integration-full
```

This command will:
1. Build and start all Docker services
2. Wait for services to be healthy
3. Run integration tests
4. Show logs if tests fail
5. Clean up and stop all services

### Manual Environment Control

For development and debugging, you can control the environment manually:

**Start the environment:**
```bash
make test-integration-up
```

**Run tests (environment must be running):**
```bash
make test-integration
```

**View logs:**
```bash
make test-integration-logs
```

**Stop the environment:**
```bash
make test-integration-down
```

### Running Specific Tests

```bash
# Run a specific test file
pytest tests/integration/test_scanner_manager_events.py -v

# Run a specific test
pytest tests/integration/test_scanner_manager_events.py::test_scanner_publishes_manager_consumes_end_to_end -v

# Run with debug logging
pytest tests/integration/ --log-cli-level=DEBUG -v
```

## Environment Configuration

The integration test environment uses `docker-compose.integration.yml` which provides:

- **Isolated Network**: All services communicate on a dedicated bridge network
- **Fast Health Checks**: 5-second intervals for quick startup
- **Test-Friendly Settings**:
  - Scanner automatic detection disabled
  - Log level set to INFO
  - Environment tag: `integration-test`

### Environment Variables

Services in the integration environment use these variables:

```bash
REDIS_URL=redis://redis:6379
RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
LOG_LEVEL=INFO
ENVIRONMENT=integration-test
```

## Integration Test Categories

### 1. Event Flow Tests (`test_scanner_manager_events.py`)
Tests the end-to-end event-driven workflow:
- Scanner publishes `SUBTITLE_REQUESTED` events
- Manager consumes events from RabbitMQ
- Manager enqueues download tasks
- Job status updates in Redis

**Key Tests:**
- ✅ `test_scanner_publishes_manager_consumes_end_to_end`
- ✅ `test_multiple_events_processed_sequentially`
- ✅ `test_consumer_ignores_non_subtitle_requested_events`
- ✅ `test_consumer_handles_malformed_events_gracefully`

### 2. Queue Publishing Tests (`test_queue_publishing.py`)
Tests RabbitMQ queue operations:
- Download queue publishing
- Translation queue publishing
- Message persistence
- Connection lifecycle

### 3. Full Publishing Flow Tests (`test_full_publishing_flow.py`)
Tests combined task and event publishing:
- Download requests with events
- Translation requests with events
- Error scenarios

## CI/CD Integration

### GitHub Actions Workflow

The integration tests run in CI using the following workflow:

```yaml
- name: Start Integration Test Environment
  run: make test-integration-up

- name: Run Integration Tests
  run: make test-integration

- name: Show logs on failure
  if: failure()
  run: make test-integration-logs

- name: Stop Integration Test Environment
  if: always()
  run: make test-integration-down
```

### Docker Compose in CI

The `docker-compose.integration.yml` file is optimized for CI environments:
- Fast health check intervals (5s)
- Short startup periods (10-15s)
- Volume cleanup on teardown
- Non-interactive mode by default

## Troubleshooting

### Tests Hang or Timeout

**Symptom**: Tests don't complete within expected time

**Solutions**:
1. Check if services are healthy:
   ```bash
   docker-compose -f docker-compose.integration.yml ps
   ```

2. View service logs:
   ```bash
   make test-integration-logs
   ```

3. Check RabbitMQ management UI: http://localhost:15672

4. Verify Redis connectivity:
   ```bash
   docker-compose -f docker-compose.integration.yml exec redis redis-cli ping
   ```

### Service Won't Start

**Symptom**: Docker service fails health checks

**Solutions**:
1. Check service logs:
   ```bash
   docker-compose -f docker-compose.integration.yml logs <service-name>
   ```

2. Rebuild images:
   ```bash
   docker-compose -f docker-compose.integration.yml build --no-cache
   ```

3. Clean up old containers and volumes:
   ```bash
   make test-integration-down
   docker system prune -f
   ```

### Port Conflicts

**Symptom**: "Port already in use" errors

**Solutions**:
1. Check what's using the ports:
   ```bash
   lsof -i :5672  # RabbitMQ
   lsof -i :6379  # Redis
   lsof -i :8000  # Manager
   lsof -i :8001  # Scanner
   ```

2. Stop conflicting services or change ports in `docker-compose.integration.yml`

### Tests Pass Locally but Fail in CI

**Common Causes**:
1. **Timing issues**: CI environments may be slower
   - Solution: Increase timeouts in tests
   
2. **Service dependencies**: Services not fully ready
   - Solution: Increase wait time or improve health checks
   
3. **Resource constraints**: CI has limited memory/CPU
   - Solution: Reduce parallel test execution

## Best Practices

### Writing Integration Tests

1. **Create Jobs in Redis First**: Always create the job before publishing events
   ```python
   job = SubtitleResponse(id=job_id, ...)
   await redis_client.save_job(job)
   await event_publisher.publish_event(event)
   ```

2. **Use Fresh Consumer Instances**: Create new consumer instances per test
   ```python
   @pytest_asyncio.fixture
   async def consumer():
       event_consumer = SubtitleEventConsumer()
       await event_consumer.connect()
       yield event_consumer
       await event_consumer.disconnect()
   ```

3. **Add Timeouts**: Always use timeouts to prevent hanging
   ```python
   await asyncio.wait_for(operation(), timeout=5.0)
   ```

4. **Clean Up Resources**: Ensure proper cleanup in fixtures
   ```python
   try:
       yield
   finally:
       await cleanup()
   ```

5. **Use Proper Markers**: Mark integration tests correctly
   ```python
   @pytest.mark.asyncio
   @pytest.mark.integration
   async def test_something():
       pass
   ```

### Performance Optimization

1. **Use `pytest-xdist` for parallel execution**:
   ```bash
   pytest -n auto tests/integration/
   ```

2. **Share fixtures across tests** with appropriate scopes:
   ```python
   @pytest_asyncio.fixture(scope="module")
   async def setup_services():
       # Setup once per module
       pass
   ```

3. **Skip slow tests in development**:
   ```bash
   pytest -m "not slow" tests/integration/
   ```

## Maintenance

### Updating Services

When adding or modifying services:

1. Update `docker-compose.integration.yml`
2. Add health checks
3. Update this documentation
4. Run full test suite to verify

### Monitoring Service Health

Health check endpoints:
- Manager: `http://localhost:8000/health`
- Scanner: `http://localhost:8001/health`
- RabbitMQ: `http://localhost:15672` (guest/guest)
- Redis: `redis-cli ping`

## Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [RabbitMQ Management](https://www.rabbitmq.com/management.html)
- [Redis Commands](https://redis.io/commands/)

