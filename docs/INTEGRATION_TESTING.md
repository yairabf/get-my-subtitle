# Integration Testing Environment

This document describes the dedicated integration testing environment for the subtitle processing system.

## Overview

The integration test environment uses `pytest-docker` to automatically manage Docker containers (RabbitMQ and Redis) for integration tests. Containers are automatically started before tests and cleaned up afterward, ensuring isolated and reliable test execution.

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

### Quick Start - Run Integration Tests

Integration tests now automatically manage Docker containers using `pytest-docker`. Simply run:

```bash
# Run all integration tests (containers managed automatically)
pytest tests/integration/ -v -m integration

# Or use the Makefile target
make test-integration
```

**No manual setup required!** The `pytest-docker` plugin automatically:
- Starts RabbitMQ and Redis containers before tests
- Waits for services to be healthy using health checks
- Sets environment variables with correct connection URLs
- Cleans up containers after tests complete (even on failure)

### Running Specific Tests

```bash
# Run a specific test file
pytest tests/integration/test_scanner_manager_events.py -v

# Run a specific test
pytest tests/integration/test_scanner_manager_events.py::test_scanner_publishes_manager_consumes_end_to_end -v

# Run with debug logging
pytest tests/integration/ --log-cli-level=DEBUG -v
```

### Manual Environment Control (Optional)

For debugging or manual testing, you can still use the full Docker Compose environment:

**Start the full environment:**
```bash
make test-integration-up
```

**View logs:**
```bash
make test-integration-logs
```

**Stop the environment:**
```bash
make test-integration-down
```

## Environment Configuration

### pytest-docker Configuration

Integration tests use `tests/integration/docker-compose.yml` which defines:
- **RabbitMQ**: Port 5672 (AMQP), 15672 (Management UI)
- **Redis**: Port 6379
- **Health Checks**: 5-second intervals for quick startup
- **Credentials**: guest/guest (RabbitMQ)

The `pytest-docker` plugin automatically:
- Maps container ports to host ports (prevents conflicts)
- Sets `RABBITMQ_URL` and `REDIS_URL` environment variables
- Waits for services to be healthy before running tests
- Uses a dedicated project name to avoid conflicts

### Environment Variables

Tests automatically receive these environment variables (set by pytest-docker fixtures):

```bash
REDIS_URL=redis://<docker_ip>:<mapped_port>
RABBITMQ_URL=amqp://guest:guest@<docker_ip>:<mapped_port>/
```

The actual values are determined dynamically by pytest-docker based on container port mappings.

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

Integration tests work seamlessly in CI/CD. pytest-docker handles all container management:

```yaml
- name: Run Integration Tests
  run: pytest tests/integration/ -v -m integration --cov=common --cov=manager
```

**No manual container setup needed!** pytest-docker automatically:
- Starts containers before tests
- Waits for services to be healthy
- Cleans up containers after tests (even on failure)

### Docker Compose in CI

The `tests/integration/docker-compose.yml` file is optimized for CI environments:
- Fast health check intervals (5s)
- Short startup periods (10s)
- Automatic cleanup on teardown
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

1. **Use pytest-docker Fixtures**: Use provided fixtures for service connections
   ```python
   async def test_something(rabbitmq_service, redis_service):
       # rabbitmq_service and redis_service are automatically available
       # They contain connection URLs and wait for services to be ready
       pass
   ```

2. **Create Jobs in Redis First**: Always create the job before publishing events
   ```python
   job = SubtitleResponse(id=job_id, ...)
   await redis_client.save_job(job)
   await event_publisher.publish_event(event)
   ```

3. **Use Fresh Consumer Instances**: Create new consumer instances per test
   ```python
   @pytest_asyncio.fixture
   async def consumer():
       event_consumer = SubtitleEventConsumer()
       await event_consumer.connect()
       yield event_consumer
       await event_consumer.disconnect()
   ```

4. **Add Timeouts**: Always use timeouts to prevent hanging
   ```python
   await asyncio.wait_for(operation(), timeout=5.0)
   ```

5. **Clean Up Resources**: Ensure proper cleanup in fixtures
   ```python
   try:
       yield
   finally:
       await cleanup()
   ```

6. **Use Proper Markers**: Mark integration tests correctly
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

