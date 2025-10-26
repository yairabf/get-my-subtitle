# Docker Compose Health Checks Implementation

## Overview

This document describes the Docker Compose health checks that have been integrated into the subtitle management system. Health checks ensure that services start in the correct order and are only marked as "healthy" once their key endpoints respond.

## Implementation Details

### Infrastructure Services

#### RabbitMQ
- **Health Check Command**: `rabbitmq-diagnostics ping`
- **Purpose**: Validates that RabbitMQ is fully started and ready to accept AMQP connections
- **Ports**: 5672 (AMQP), 15672 (Management UI)

#### Redis
- **Health Check Command**: `redis-cli ping`
- **Purpose**: Validates that Redis server is accepting connections
- **Port**: 6379

### Application Services

#### Manager (FastAPI API Server)
- **Health Check Command**: `curl -f http://localhost:8000/health`
- **Purpose**: HTTP health endpoint validation
- **Port**: 8000
- **Dependencies**: Waits for Redis and RabbitMQ to be healthy
- **Special Note**: Dockerfile updated to include `curl` for health checks

#### Downloader Worker
- **Health Check Command**: Python one-liner to test Redis connection
- **Purpose**: Validates worker can connect to Redis infrastructure
- **Dependencies**: Waits for Manager to be healthy
- **No Exposed Ports**: Background worker service

#### Translator Worker
- **Health Check Command**: Python one-liner to test Redis connection
- **Purpose**: Validates worker can connect to Redis infrastructure
- **Dependencies**: Waits for Manager to be healthy
- **No Exposed Ports**: Background worker service

## Health Check Parameters

All services use standardized health check parameters:

```yaml
interval: 10s      # Check every 10 seconds
timeout: 5s        # 5 second timeout per check
retries: 3         # Mark unhealthy after 3 consecutive failures
start_period: 30s  # Grace period for initial startup
```

## Startup Sequence

Services start in this dependency order:

```
1. Redis + RabbitMQ (in parallel)
   ↓ (both must be healthy)
2. Manager
   ↓ (must be healthy)
3. Downloader + Translator (in parallel)
```

## Testing the Health Checks

### Start All Services

```bash
docker-compose up -d
```

### Monitor Health Status

```bash
# Watch all services starting up
docker-compose ps

# Watch in real-time (refreshes every 2 seconds)
watch -n 2 docker-compose ps
```

### Check Individual Service Health

```bash
# Check RabbitMQ health
docker-compose exec rabbitmq rabbitmq-diagnostics ping

# Check Redis health
docker-compose exec redis redis-cli ping

# Check Manager health (via curl)
curl http://localhost:8000/health

# Check Manager health (from inside container)
docker-compose exec manager curl -f http://localhost:8000/health
```

### View Service Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f manager
docker-compose logs -f downloader
docker-compose logs -f translator
```

### Verify Startup Order

```bash
# Check Docker events in real-time to see startup sequence
docker events --filter 'type=container'
```

### Test Health Check Failure Recovery

```bash
# Stop Redis and watch dependent services become unhealthy
docker-compose stop redis
docker-compose ps

# Restart Redis and watch services recover
docker-compose start redis
watch -n 2 docker-compose ps
```

## Expected Behavior

### Successful Startup
1. Redis and RabbitMQ start first and become healthy within ~30 seconds
2. Manager starts after dependencies are healthy, becomes healthy within ~30 seconds
3. Downloader and Translator start after Manager is healthy
4. All services show `(healthy)` status in `docker-compose ps`

### Health Status in docker-compose ps

```
NAME                              STATUS
get-my-subtitle-rabbitmq-1        Up 2 minutes (healthy)
get-my-subtitle-redis-1           Up 2 minutes (healthy)
get-my-subtitle-manager-1         Up 1 minute (healthy)
get-my-subtitle-downloader-1      Up 30 seconds (healthy)
get-my-subtitle-translator-1      Up 30 seconds (healthy)
```

### Failure Scenarios

**If a service fails health checks:**
- Status will show `(unhealthy)` in `docker-compose ps`
- Docker can be configured to restart unhealthy containers
- Dependent services will not start until dependencies are healthy

**Common failure causes:**
- Missing `.env` file with required environment variables
- Port conflicts (8000, 5672, 6379, 15672)
- Network connectivity issues
- Missing dependencies in Docker images

## Environment Configuration

Ensure you have a `.env` file based on `env.template`:

```bash
cp env.template .env
# Edit .env with your configuration
```

**Critical environment variables:**
- `REDIS_URL` - Overridden in docker-compose.yml to use service name
- `RABBITMQ_URL` - Overridden in docker-compose.yml to use service name
- `OPENAI_API_KEY` - Required for translator service
- `API_HOST` and `API_PORT` - Manager API configuration

## Benefits

1. **Automatic Startup Ordering**: Services start only when dependencies are ready
2. **Reliability**: Unhealthy containers can be automatically restarted
3. **Debugging**: Quick status overview with `docker-compose ps`
4. **Orchestration Ready**: External tools can wait for "healthy" status
5. **Production Ready**: Proper health monitoring for deployments

## Troubleshooting

### Service stays in "starting" state
- Check logs: `docker-compose logs <service-name>`
- Verify `.env` file exists and contains required variables
- Ensure ports are not already in use

### Health check fails immediately
- Verify health check command works manually inside container
- Check if service has necessary dependencies (e.g., curl for Manager)
- Review service logs for startup errors

### Dependent services don't start
- Ensure parent services show `(healthy)` status
- Check for `depends_on` conditions in docker-compose.yml
- Verify Docker Compose version supports health check conditions (3.8+)

## Docker Compose Commands Reference

```bash
# Start all services with health checks
docker-compose up -d

# View status with health information
docker-compose ps

# Stop all services
docker-compose down

# Rebuild and restart services
docker-compose up -d --build

# View logs for all services
docker-compose logs -f

# Restart a specific service
docker-compose restart <service-name>

# Check service health manually
docker-compose exec <service-name> <health-check-command>
```

## Next Steps

After verifying health checks work correctly:
1. Test the complete workflow (subtitle request → download → translation)
2. Monitor health status during actual workload processing
3. Configure restart policies if needed
4. Consider adding health check metrics to monitoring systems

