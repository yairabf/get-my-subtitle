# RabbitMQ Health Monitoring - Testing Guide

## Pre-Implementation Verification

### Code Quality Checks ✅

1. **Syntax Validation**: All Python files compile without errors
   ```bash
   python3 -m py_compile src/manager/*.py
   ```
   - ✅ orchestrator.py - No errors
   - ✅ event_consumer.py - No errors (syntax warning fixed)
   - ✅ health.py - No errors
   - ✅ main.py - No errors

2. **Linter Checks**: No linting errors found
   ```
   ReadLints on all modified files: PASSED
   ```

3. **Import Structure**: All imports are correct and follow existing patterns

## Testing Strategy

### 1. Unit Testing (Recommended)

#### Test Orchestrator Health Monitoring

Create test file: `tests/manager/test_orchestrator_health.py`

```python
import pytest
from unittest.mock import AsyncMock, Mock, patch
from manager.orchestrator import SubtitleOrchestrator

@pytest.mark.asyncio
async def test_is_healthy_when_connected():
    """Test is_healthy returns True when connection and channel exist."""
    orchestrator = SubtitleOrchestrator()
    orchestrator.connection = Mock(is_closed=False)
    orchestrator.channel = Mock()
    
    assert await orchestrator.is_healthy() is True

@pytest.mark.asyncio
async def test_is_healthy_when_connection_closed():
    """Test is_healthy returns False when connection is closed."""
    orchestrator = SubtitleOrchestrator()
    orchestrator.connection = Mock(is_closed=True)
    orchestrator.channel = Mock()
    
    assert await orchestrator.is_healthy() is False

@pytest.mark.asyncio
async def test_is_healthy_when_no_channel():
    """Test is_healthy returns False when channel is None."""
    orchestrator = SubtitleOrchestrator()
    orchestrator.connection = Mock(is_closed=False)
    orchestrator.channel = None
    
    assert await orchestrator.is_healthy() is False

@pytest.mark.asyncio
async def test_ensure_connected_when_healthy():
    """Test ensure_connected returns True without reconnecting when healthy."""
    orchestrator = SubtitleOrchestrator()
    orchestrator.connection = Mock(is_closed=False)
    orchestrator.channel = Mock()
    
    result = await orchestrator.ensure_connected()
    
    assert result is True

@pytest.mark.asyncio
async def test_ensure_connected_triggers_reconnect():
    """Test ensure_connected triggers reconnection when unhealthy."""
    orchestrator = SubtitleOrchestrator()
    orchestrator.connection = None
    orchestrator.channel = None
    
    with patch.object(orchestrator, 'reconnect', new_callable=AsyncMock) as mock_reconnect:
        await orchestrator.ensure_connected()
        mock_reconnect.assert_called_once()

@pytest.mark.asyncio
async def test_connect_with_retry_logic():
    """Test connect method retries on failure."""
    orchestrator = SubtitleOrchestrator()
    
    with patch('manager.orchestrator.aio_pika.connect_robust') as mock_connect:
        # Simulate failure then success
        mock_connect.side_effect = [
            Exception("Connection failed"),
            Mock(is_closed=False)
        ]
        
        await orchestrator.connect(max_retries=3, retry_delay=0.1)
        
        assert mock_connect.call_count == 2
```

#### Test Event Consumer Health Monitoring

Create test file: `tests/manager/test_event_consumer_health.py`

```python
import pytest
from unittest.mock import AsyncMock, Mock, patch
from manager.event_consumer import SubtitleEventConsumer

@pytest.mark.asyncio
async def test_is_healthy_when_all_checks_pass():
    """Test is_healthy returns True when all components are healthy."""
    consumer = SubtitleEventConsumer()
    consumer.connection = Mock(is_closed=False)
    consumer.channel = Mock()
    consumer.exchange = Mock()
    consumer.queue = Mock()
    consumer.is_consuming = True
    
    with patch('manager.event_consumer.redis_client.ensure_connected', return_value=True):
        assert await consumer.is_healthy() is True

@pytest.mark.asyncio
async def test_is_healthy_when_connection_closed():
    """Test is_healthy returns False when connection is closed."""
    consumer = SubtitleEventConsumer()
    consumer.connection = Mock(is_closed=True)
    consumer.channel = Mock()
    
    assert await consumer.is_healthy() is False

@pytest.mark.asyncio
async def test_is_healthy_when_not_consuming():
    """Test is_healthy returns False when not consuming."""
    consumer = SubtitleEventConsumer()
    consumer.connection = Mock(is_closed=False)
    consumer.channel = Mock()
    consumer.exchange = Mock()
    consumer.queue = Mock()
    consumer.is_consuming = False
    
    assert await consumer.is_healthy() is False

@pytest.mark.asyncio
async def test_is_healthy_when_redis_unhealthy():
    """Test is_healthy returns False when Redis is unhealthy."""
    consumer = SubtitleEventConsumer()
    consumer.connection = Mock(is_closed=False)
    consumer.channel = Mock()
    consumer.exchange = Mock()
    consumer.queue = Mock()
    consumer.is_consuming = True
    
    with patch('manager.event_consumer.redis_client.ensure_connected', return_value=False):
        assert await consumer.is_healthy() is False

@pytest.mark.asyncio
async def test_start_consuming_with_reconnection_loop():
    """Test start_consuming implements reconnection loop."""
    consumer = SubtitleEventConsumer()
    
    with patch.object(consumer, 'connect', new_callable=AsyncMock) as mock_connect:
        with patch.object(consumer, '_consume_with_health_monitoring', new_callable=AsyncMock) as mock_consume:
            # Simulate one consumption cycle then stop
            async def side_effect():
                consumer._should_stop = True
            mock_consume.side_effect = side_effect
            
            await consumer.start_consuming()
            
            mock_connect.assert_called()
            mock_consume.assert_called()
```

#### Test Health Check Module

Create test file: `tests/manager/test_health.py`

```python
import pytest
from unittest.mock import AsyncMock, Mock, patch
from manager.health import check_health

@pytest.mark.asyncio
async def test_check_health_all_healthy():
    """Test check_health returns healthy status when all components are healthy."""
    with patch('manager.health.orchestrator.is_healthy', return_value=True):
        with patch('manager.health.event_consumer.is_healthy', return_value=True):
            with patch('manager.health.event_publisher._check_health', return_value=True):
                with patch('manager.health.redis_client.ensure_connected', return_value=True):
                    result = await check_health()
                    
                    assert result['status'] == 'healthy'
                    assert all(result['checks'].values())

@pytest.mark.asyncio
async def test_check_health_orchestrator_unhealthy():
    """Test check_health returns unhealthy when orchestrator is unhealthy."""
    with patch('manager.health.orchestrator.is_healthy', return_value=False):
        with patch('manager.health.event_consumer.is_healthy', return_value=True):
            with patch('manager.health.event_publisher._check_health', return_value=True):
                with patch('manager.health.redis_client.ensure_connected', return_value=True):
                    result = await check_health()
                    
                    assert result['status'] == 'unhealthy'
                    assert result['checks']['orchestrator_connected'] is False

@pytest.mark.asyncio
async def test_check_health_includes_details():
    """Test check_health includes detailed component information."""
    with patch('manager.health.orchestrator.is_healthy', return_value=True):
        with patch('manager.health.event_consumer.is_healthy', return_value=True):
            with patch('manager.health.event_publisher._check_health', return_value=True):
                with patch('manager.health.redis_client.ensure_connected', return_value=True):
                    result = await check_health()
                    
                    assert 'details' in result
                    assert 'orchestrator' in result['details']
                    assert 'event_consumer' in result['details']
                    assert 'event_publisher' in result['details']
                    assert 'redis' in result['details']
```

### 2. Integration Testing

#### Test RabbitMQ Reconnection

**Test Scenario 1: Orchestrator Reconnection**

```bash
# Terminal 1: Start services
docker-compose up -d

# Terminal 2: Watch manager logs
docker logs -f manager

# Terminal 3: Simulate RabbitMQ failure
docker stop rabbitmq

# Expected in logs:
# - Connection errors
# - "Orchestrator connection unhealthy, attempting to reconnect..."
# - Retry attempts with increasing delays

# Restart RabbitMQ
docker start rabbitmq

# Expected in logs:
# - "✅ Orchestrator reconnection successful"
# - "✅ Orchestrator connected to RabbitMQ successfully"
```

**Test Scenario 2: Event Consumer Reconnection**

```bash
# Terminal 1: Monitor event consumer
docker logs -f manager | grep -i "consumer"

# Terminal 2: Stop RabbitMQ
docker stop rabbitmq

# Expected in logs:
# - "❌ Error in event consumer (failure #1)"
# - "Attempting to reconnect in 3.0s..."
# - Multiple reconnection attempts

# Restart RabbitMQ
docker start rabbitmq

# Expected in logs:
# - "Connected to RabbitMQ - Queue 'manager.subtitle.requests' bound to exchange 'subtitle.events'"
# - "🎧 Starting to consume SUBTITLE_REQUESTED events..."
```

**Test Scenario 3: Exponential Backoff**

```bash
# Keep RabbitMQ stopped for extended period
docker stop rabbitmq

# Monitor logs for delay pattern:
# Attempt 1: "Attempting to reconnect in 3.0s..."
# Attempt 2: "Attempting to reconnect in 3.0s..."
# Attempt 3: "Attempting to reconnect in 3.0s..."
# After 3 consecutive failures:
# "❌ Too many consecutive failures (3), increasing reconnect delay to 6.0s"
# Attempt 4: "Attempting to reconnect in 6.0s..."
# Continue pattern up to max delay of 30.0s
```

### 3. Health Endpoint Testing

#### Test Health Endpoints with curl

```bash
# 1. Test comprehensive health check
curl http://localhost:8000/health | jq

# Expected output:
{
  "status": "healthy",
  "checks": {
    "orchestrator_connected": true,
    "event_consumer_connected": true,
    "event_consumer_consuming": true,
    "event_publisher_connected": true,
    "redis_connected": true
  },
  "details": {
    "orchestrator": {...},
    "event_consumer": {...},
    "event_publisher": {...},
    "redis": {...}
  }
}

# 2. Test orchestrator-specific health
curl http://localhost:8000/health/orchestrator | jq

# Expected output:
{
  "status": "healthy",
  "connected": true,
  "has_channel": true,
  "download_queue": "subtitle.download",
  "translation_queue": "subtitle.translation"
}

# 3. Test consumer-specific health
curl http://localhost:8000/health/consumer | jq

# Expected output:
{
  "status": "healthy",
  "is_consuming": true,
  "connected": true,
  "queue_name": "manager.subtitle.requests",
  "routing_key": "subtitle.requested"
}

# 4. Test health during RabbitMQ outage
docker stop rabbitmq
sleep 5
curl http://localhost:8000/health | jq

# Expected: Some checks should be false, status should be "unhealthy"
```

### 4. Load Testing

#### Test Under Load with Concurrent Requests

```bash
# Use Apache Bench to send concurrent requests
ab -n 1000 -c 10 http://localhost:8000/health

# Expected:
# - All requests should succeed (200 OK)
# - No race conditions in reconnection logic
# - Health checks should remain accurate
```

### 5. Chaos Engineering (Advanced)

#### Random Connection Failures

```bash
# Script to randomly stop/start RabbitMQ
while true; do
    sleep $((RANDOM % 30 + 10))  # Wait 10-40 seconds
    docker stop rabbitmq
    sleep $((RANDOM % 10 + 5))   # Down for 5-15 seconds
    docker start rabbitmq
done

# Monitor manager logs for:
# - Successful reconnections
# - No message loss (if possible)
# - Proper health status reporting
```

## Verification Checklist

- ✅ **Code Quality**
  - [x] No syntax errors
  - [x] No linter errors
  - [x] Follows existing code patterns
  - [x] Proper type hints
  - [x] Comprehensive logging

- ✅ **Orchestrator Health Monitoring**
  - [x] `is_healthy()` method implemented
  - [x] `ensure_connected()` method implemented
  - [x] `reconnect()` method with retry logic
  - [x] All enqueue methods use `ensure_connected()`
  - [x] Configuration settings used correctly

- ✅ **Event Consumer Health Monitoring**
  - [x] `is_healthy()` method implemented
  - [x] Automatic reconnection loop in `start_consuming()`
  - [x] Periodic health checks during consumption
  - [x] Exponential backoff implemented
  - [x] Graceful shutdown with `_should_stop` flag

- ✅ **Health Check Module**
  - [x] Checks all components (orchestrator, consumer, publisher, Redis)
  - [x] Returns detailed status information
  - [x] Properly integrated with main.py
  - [x] Multiple health endpoints available

- ✅ **Configuration**
  - [x] Uses settings from `common.config.py`
  - [x] All timing parameters configurable
  - [x] Consistent with other workers

- ⏳ **Testing** (To be performed)
  - [ ] Unit tests for all new methods
  - [ ] Integration tests for reconnection
  - [ ] Health endpoint tests
  - [ ] Load tests
  - [ ] Chaos engineering tests

## Expected Behavior Summary

### Normal Operation
- All health checks return `True`
- Health endpoint shows all components "healthy"
- No reconnection attempts in logs
- Messages processed successfully

### During RabbitMQ Outage
- Health checks detect connection loss
- Automatic reconnection attempts begin
- Exponential backoff applied after consecutive failures
- Health endpoint shows components "unhealthy"
- Services continue in mock mode (graceful degradation)

### After RabbitMQ Recovery
- Reconnection succeeds within configured retry limits
- Health checks return to `True`
- Health endpoint shows all components "healthy"
- Normal message processing resumes

## Performance Expectations

### Health Check Performance
- Health check should complete in < 100ms
- No blocking operations in health check methods
- Concurrent health checks should not cause issues

### Reconnection Performance
- Initial reconnection attempt: 3 seconds
- Maximum reconnection delay: 30 seconds
- Total reconnection time: Depends on outage duration
  - Short outage (< 30s): Single reconnection cycle
  - Medium outage (30s - 5min): Multiple cycles with backoff
  - Long outage (> 5min): Continues until success or service restart

## Troubleshooting Guide

### Issue: Health checks always return False
**Possible causes:**
1. RabbitMQ is actually down - check `docker ps`
2. Configuration incorrect - verify `rabbitmq_url` setting
3. Connection never established - check startup logs

### Issue: Reconnection not working
**Possible causes:**
1. Max retries reached - increase `rabbitmq_reconnect_max_retries`
2. Network issue - check Docker network configuration
3. Lock contention - check for deadlocks in logs

### Issue: Exponential backoff not increasing
**Possible causes:**
1. Not enough consecutive failures - requires 3+ failures
2. Settings misconfigured - check `rabbitmq_reconnect_max_delay`
3. Successful connections resetting counter (expected behavior)

## Conclusion

The implementation is complete and ready for testing. All code quality checks have passed. The system follows established patterns and is consistent with other workers. Manual testing should be performed to verify reconnection behavior under various failure scenarios.

