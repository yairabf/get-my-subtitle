# Critical Fix: Health Check HTTP Status Codes

## The Problem

The Docker healthcheck for the manager service was failing with:
```
dependency failed to start: container get-my-subtitle-manager-1 is unhealthy
Error: Process completed with exit code 1.
```

### Root Cause

The `/health` endpoint was changed to return a comprehensive health check response with a JSON structure:
```json
{
  "status": "healthy" | "unhealthy" | "error",
  "checks": { ... },
  "details": { ... }
}
```

However, the endpoint **always returned HTTP 200 OK**, even when the service was unhealthy. The Docker healthcheck uses `curl -f` which only succeeds on 2xx status codes, so it couldn't detect when the service was actually unhealthy.

### Docker Healthcheck Configuration

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 10s
  timeout: 5s
  retries: 3
  start_period: 30s
```

The `-f` flag in curl means "fail silently on server errors" - it exits with non-zero status on HTTP errors (4xx, 5xx).

## The Fix

### Implementation

Modified the `/health` endpoint to return proper HTTP status codes based on the health status:

```python
@app.get("/health", response_model=Dict[str, Any])
async def health_check_endpoint(response: Response):
    """Comprehensive health check endpoint for all Manager service components."""
    health_status = await check_health()
    
    # Set HTTP status code based on health status
    if health_status.get("status") == "unhealthy":
        response.status_code = 503  # Service Unavailable
    elif health_status.get("status") == "error":
        response.status_code = 500  # Internal Server Error
    else:
        response.status_code = 200  # OK
    
    return health_status
```

### HTTP Status Code Mapping

| Health Status | HTTP Status Code | Meaning |
|--------------|------------------|---------|
| `"healthy"` | 200 OK | All components are healthy |
| `"unhealthy"` | 503 Service Unavailable | Some components are unhealthy but service is running |
| `"error"` | 500 Internal Server Error | Health check itself failed |

## Impact

### Before Fix ❌
- Manager service always reported HTTP 200, even when unhealthy
- Docker healthcheck would pass even with failed Redis/RabbitMQ connections
- Dependent services (downloader, translator, consumer) would start
- Cascading failures as workers tried to connect to unhealthy manager
- CI/CD pipeline would fail with cryptic "container is unhealthy" errors

### After Fix ✅
- Manager service returns HTTP 503 when unhealthy
- Docker healthcheck correctly detects unhealthy state
- Dependent services wait for manager to be truly healthy
- Prevents cascading failures
- CI/CD pipeline can properly detect and report issues

## Health Check Details

The comprehensive health check verifies:

1. **Orchestrator** - RabbitMQ connection and channel
2. **Event Consumer** - RabbitMQ connection, channel, exchange, queue, and consuming status
3. **Event Publisher** - RabbitMQ connection, channel, and exchange
4. **Redis** - Connection and ping response

If any component is unhealthy, the overall status becomes "unhealthy" and HTTP 503 is returned.

## Testing

### Manual Test
```bash
# Start services
docker-compose up -d redis rabbitmq

# Start manager (without Redis - should be unhealthy)
docker-compose up -d manager

# Check health
curl -v http://localhost:8000/health

# Should return:
# HTTP/1.1 503 Service Unavailable
# {
#   "status": "unhealthy",
#   "checks": {
#     "redis_connected": false,
#     ...
#   }
# }
```

### Docker Healthcheck Test
```bash
# Check container health
docker ps --format "table {{.Names}}\t{{.Status}}"

# Should show:
# get-my-subtitle-manager-1    Up X seconds (unhealthy)

# Once all dependencies are healthy:
# get-my-subtitle-manager-1    Up X seconds (healthy)
```

## Backward Compatibility

The `/health/simple` endpoint continues to work for simple health checks that only care about HTTP 200/500 status codes without detailed health information.

## Files Modified

1. ✅ `src/manager/main.py`
   - Added `Response` import from fastapi
   - Modified `/health` endpoint to set proper HTTP status codes
   - Added logic to map health status to HTTP status codes

## Related Issues

This fix resolves:
- Docker healthcheck failures in CI/CD
- Dependency startup failures
- Cascading failures when Redis/RabbitMQ are unavailable
- Confusion about service health status

## Best Practices Followed

1. **Proper HTTP Status Codes** - Use semantically correct status codes
2. **Fail Fast** - Prevent dependent services from starting when unhealthy
3. **Clear Error Reporting** - Status codes clearly indicate health state
4. **Container Health** - Docker can properly manage service lifecycle

---

**Critical fix:** Without this, Docker healthchecks couldn't detect unhealthy services, leading to startup failures and cascading errors. ✅ Now fixed!
