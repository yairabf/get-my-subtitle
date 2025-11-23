# Testing Guide

This guide provides comprehensive testing guidance, from quick verification to full integration testing.

> **📖 See Also**: [Main README](../README.md) for project overview and [Development Guide](DEVELOPMENT.md) for development setup.

## Table of Contents

- [Quick Test Start](#quick-test-start)
- [Running Tests](#running-tests)
- [Manual Testing Guide](#manual-testing-guide)
- [Test Flow Diagrams](#test-flow-diagrams)
- [Integration Testing](#integration-testing)
- [Test Checklist](#test-checklist)
- [Performance Testing](#performance-testing)
- [Testing Tools](#testing-tools)

## Quick Test Start

Get up and running with testing in 5 minutes:

### 1. Prerequisites Check
```bash
# Make sure Docker is running
docker ps

# Check you have the .env file
ls -la .env || cp env.template .env
```

### 2. Start Services (30 seconds)
```bash
# Clean start
docker-compose down -v

# Build and start all services
docker-compose up --build -d

# Wait for services to be healthy (30-60 seconds)
sleep 30
```

### 3. Verify Health (10 seconds)
```bash
# Quick health check
curl http://localhost:8000/health

# Expected: {"status": "ok"}
```

### 4. Submit Test Job (5 seconds)
```bash
curl -X POST http://localhost:8000/subtitles/download \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://example.com/video.mp4",
    "video_title": "Test Video",
    "language": "en",
    "preferred_sources": ["opensubtitles"]
  }'
```

### 5. Watch Progress (15-30 seconds)
```bash
# Replace {job_id} with actual job ID from step 4
watch -n 2 'curl -s http://localhost:8000/subtitles/{job_id}/status | jq'

# Expected progression:
# DOWNLOAD_QUEUED → DOWNLOAD_IN_PROGRESS → DONE
```

### 6. Check Results (5 seconds)
```bash
# View job details and events
curl http://localhost:8000/subtitles/{job_id}/events | jq

# You should see:
# - Final status: DONE
# - Event history with all events
# - Complete timeline of what happened
```

## Running Tests

### Unit Tests
```bash
# Run all unit tests
make test-unit

# Run with coverage
pytest tests/ -m "not integration" --cov=common --cov=manager --cov=downloader --cov=translator --cov-report=html

# Run specific test file
pytest tests/common/test_utils.py -v

# Run specific test
pytest tests/common/test_utils.py::test_function_name -v
```

### Integration Tests

Integration tests verify connections between all services (Manager, Consumer, Downloader, Translator, Scanner) using the full Docker environment.

**What Integration Tests Cover:**
- Event flow: Scanner → Manager → Downloader → Consumer → Redis
- Event flow: Manager → Translator → Consumer → Redis
- RabbitMQ message routing and exchange bindings
- Redis state updates from Consumer service
- Service-to-service communication
- Event history tracking

**What Integration Tests DON'T Cover:**
- External API calls (OpenSubtitles, OpenAI) - covered in E2E tests
- Actual subtitle downloads - mocked in integration tests
- Actual translations - mocked in integration tests

**Prerequisites:**
- Docker and Docker Compose installed
- No services running on ports 5672 (RabbitMQ), 6379 (Redis), 8000 (Manager)

**Running Integration Tests Locally:**

```bash
# Option 1: Automatic (recommended)
# Starts Docker environment, runs tests, tears down
make test-integration-full

# Option 2: Manual control
# Start environment
make test-integration-up

# Run tests (in another terminal)
pytest tests/integration/ -v -m integration

# View logs if tests fail
make test-integration-logs

# Stop environment
make test-integration-down
```

**Integration Test Environment:**

Uses `docker-compose.integration.yml` which includes:
- RabbitMQ (message broker)
- Redis (state storage)
- Manager (API + orchestration)
- Consumer (event processor)
- Downloader (with mocked OpenSubtitles)
- Translator (with mocked OpenAI)
- Scanner (disabled auto-scan)

**Debugging Integration Tests:**

```bash
# View service logs
docker-compose -f docker-compose.integration.yml logs -f manager consumer

# Check service health
docker-compose -f docker-compose.integration.yml ps

# Inspect RabbitMQ
open http://localhost:15672  # guest/guest

# Inspect Redis
docker-compose -f docker-compose.integration.yml exec redis redis-cli
```

**CI Integration:**

In CI (GitHub Actions), services are provided automatically. Tests connect to:
- `localhost:5672` (RabbitMQ)
- `localhost:6379` (Redis)

### Test Coverage
```bash
# Generate coverage report
make test-cov

# Open HTML report
open htmlcov/index.html

# Or use invoke
invoke coverage-html
```

## Manual Testing Guide

### Test Scenarios

**1. Infrastructure Health Check**
```bash
# Start all services
docker-compose up --build -d

# Wait for services to be healthy
docker-compose ps

# Verify each service
curl http://localhost:8000/health
open http://localhost:15672  # RabbitMQ UI
docker exec -it get-my-subtitle-redis-1 redis-cli ping
```

**2. Subtitle Download Flow (Subtitle Found)**
```bash
# Submit download request
curl -X POST http://localhost:8000/subtitles/download \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://example.com/video.mp4",
    "video_title": "Test Video",
    "language": "he",
    "preferred_sources": ["opensubtitles"]
  }'

# Monitor status
watch -n 2 'curl -s http://localhost:8000/subtitles/{job_id}/status | jq'

# Check event history
curl http://localhost:8000/subtitles/{job_id}/events | jq
```

**3. Translation Flow (Subtitle Not Found)**
```bash
# Submit request that will trigger translation
# (Use a video title that likely has no subtitles)

# Monitor for translation flow
docker-compose logs -f downloader | grep "not found"

# Check status progression
# DOWNLOAD_QUEUED → DOWNLOAD_IN_PROGRESS → TRANSLATE_QUEUED → TRANSLATE_IN_PROGRESS → DONE
```

**4. Error Handling**
```bash
# Test invalid job ID
curl http://localhost:8000/subtitles/00000000-0000-0000-0000-000000000000/status
# Expected: 404 Not Found

# Test invalid request body
curl -X POST http://localhost:8000/subtitles/download \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://example.com/video.mp4"}'
# Expected: 422 Validation Error
```

**5. RabbitMQ Event Verification**
```bash
# Open RabbitMQ Management UI
open http://localhost:15672  # Login: guest/guest

# Verify Exchange: subtitle.events exists
# Verify Queue: subtitle.events.consumer has consumer
# Check message rates and bindings
```

**6. Redis State Verification**
```bash
# Connect to Redis
docker exec -it get-my-subtitle-redis-1 redis-cli

# List all jobs
KEYS job:*

# Get job data
GET job:{job_id}

# Get event history
LRANGE job:events:{job_id} 0 -1
```

## Test Flow Diagrams

### Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                            YOUR TESTING                              │
│                                                                       │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐      │
│  │  Submit Job  │ ───> │  Watch Job   │ ───> │ Check Events │      │
│  │  (curl POST) │      │  (curl GET)  │      │  (curl GET)  │      │
│  └──────────────┘      └──────────────┘      └──────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       MANAGER API (Port 8000)                        │
│  POST /subtitles/download  │  GET /status  │  GET /events           │
└─────────────────────────────────────────────────────────────────────┘
          │                                              ▲
          │ Creates Job                                  │ Reads Events
          ▼                                              │
┌─────────────────────────────────────────────────────────────────────┐
│                       REDIS (Port 6379)                              │
│  ┌──────────────────┐         ┌──────────────────────────────┐     │
│  │  Job Data        │         │  Event History               │     │
│  │  job:{id}        │         │  job:events:{id}             │     │
│  └──────────────────┘         └──────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
          │                                              ▲
          │ Enqueues Task                                │ Updates State
          ▼                                              │
┌─────────────────────────────────────────────────────────────────────┐
│                    RABBITMQ (Ports 5672, 15672)                      │
│  Exchange: subtitle.events (topic)                                   │
│  Queue: subtitle.events.consumer                                     │
└─────────────────────────────────────────────────────────────────────┘
          │                    │                    │
    ┌─────▼─────┐       ┌──────▼──────┐      ┌────▼──────┐
    │ Downloader│       │ Translator  │      │ Consumer  │
    │  Worker   │       │   Worker    │      │  Service  │
    └───────────┘       └─────────────┘      └───────────┘
```

### Status Transitions

```
DOWNLOAD_QUEUED ──────────> DOWNLOAD_IN_PROGRESS
                                     │
                    ┌────────────────┴────────────────┐
                    │                                 │
              Subtitle Found               Subtitle Not Found
                    │                                 │
                    ▼                                 ▼
                  DONE                      TRANSLATE_QUEUED
                                                     │
                                                     ▼
                                          TRANSLATE_IN_PROGRESS
                                                     │
                                                     ▼
                                                   DONE

                            Any Stage
                                │
                                │ Error
                                ▼
                            FAILED
```

## Integration Testing

### Environment Setup

**Docker Compose Files:**
- `docker-compose.yml` - Main/Production (all services)
- `docker-compose.integration.yml` - Full integration test environment
- `tests/integration/docker-compose.yml` - Minimal (infrastructure only)

**Quick Start:**
```bash
# Run all integration tests (containers managed automatically)
pytest tests/integration/ -v -m integration

# Or use Makefile
make test-integration
```

**Manual Environment Control:**
```bash
# Start full integration environment
make test-integration-up

# View logs
make test-integration-logs

# Stop environment
make test-integration-down
```

### Integration Test Categories

1. **Event Flow Tests** - End-to-end event-driven workflow
2. **Queue Publishing Tests** - RabbitMQ queue operations
3. **Full Publishing Flow Tests** - Combined task and event publishing

### CI/CD Integration

Integration tests work seamlessly in CI/CD:
- **GitHub Actions**: Services provided automatically
- **Local**: Start services with `make up-infra` before running tests

## Test Checklist

Use this checklist to track your testing progress:

- [ ] **Infrastructure**
  - [ ] All services start successfully
  - [ ] Health checks pass
  - [ ] RabbitMQ exchange created
  - [ ] Redis connection works

- [ ] **Download Flow**
  - [ ] Job submitted successfully
  - [ ] Status progresses correctly
  - [ ] Events published to RabbitMQ
  - [ ] Consumer processes events
  - [ ] Final status is DONE

- [ ] **Translation Flow**
  - [ ] Job transitions to translation
  - [ ] Translator processes task
  - [ ] Translation event published
  - [ ] Final status is DONE

- [ ] **Event System**
  - [ ] Events stored in Redis
  - [ ] Event history endpoint works
  - [ ] Events in correct order
  - [ ] All event types present

- [ ] **Error Handling**
  - [ ] Invalid job ID returns 404
  - [ ] Invalid request returns 422
  - [ ] Services handle failures gracefully
  - [ ] Meaningful error messages

## Performance Testing

### Load Testing
```bash
# Submit 10 concurrent jobs
for i in {1..10}; do
  curl -X POST http://localhost:8000/subtitles/download \
    -H "Content-Type: application/json" \
    -d "{
      \"video_url\": \"https://example.com/video$i.mp4\",
      \"video_title\": \"Load Test Video $i\",
      \"language\": \"en\",
      \"preferred_sources\": [\"opensubtitles\"]
    }" &
done
wait
```

### Expected Performance

**Subtitle Found Flow:**
- Job submission: < 100ms
- Status update (queued → in_progress): ~1s
- Download completion: ~2-3s
- Event processing: < 500ms
- **Total: ~3-4 seconds**

**Translation Flow:**
- Job submission: < 100ms
- Download attempt: ~2s
- Translation queued: ~500ms
- Translation processing: ~3-5s
- Event processing: < 500ms
- **Total: ~6-8 seconds**

## Testing Tools

**Scripts:**
- `./scripts/test_manual.sh` - Manual testing helper script
- `./scripts/ci_code_quality.sh` - Code quality checks
- `./scripts/ci_run_tests.sh` - Test execution

**Useful Commands:**
```bash
# Health check
./scripts/test_manual.sh check-health

# Submit test job
./scripts/test_manual.sh submit-job

# Watch job progress
./scripts/test_manual.sh watch-job <job_id>

# Load test
./scripts/test_manual.sh load-test 10
```

For more detailed testing information, see:
- [Logging Documentation](LOGGING.md) - Logging configuration and usage
- Service-specific READMEs for service-specific testing



