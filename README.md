# Get My Subtitle

[![CI](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/ci.yml/badge.svg)](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/ci.yml)
[![Lint](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/lint.yml/badge.svg)](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/lint.yml)
[![codecov](https://codecov.io/gh/yairabramovitch/get-my-subtitle/branch/main/graph/badge.svg)](https://codecov.io/gh/yairabramovitch/get-my-subtitle)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A microservices-based subtitle management system that fetches, translates, and manages subtitles for videos.

## Architecture

This project consists of multiple microservices working together:

- **Manager**: FastAPI-based API server and orchestrator
- **Downloader**: Worker service for fetching subtitles from various sources
- **Translator**: Worker service for translating subtitles
- **Scanner**: Media detection service (WebSocket, webhook, file system monitoring)
- **Consumer**: Event consumer service that processes events and updates job states
- **Common**: Shared schemas, utilities, and configuration

### System Flow

```
Client Request
      ↓
Manager (publishes event) → RabbitMQ Topic Exchange
      ↓                              ↓
Work Queue                     Event Queue
      ↓                              ↓
Downloader (publishes event) → Consumer
      ↓                              ↓
Translation Queue              Redis (status + events)
      ↓
Translator (publishes event) → Consumer
                                     ↓
                               Redis (status + events)
```

### Event-Driven Architecture

The system uses an event-driven architecture where:
- Services publish events to RabbitMQ topic exchange (`subtitle.events`)
- Consumer service processes events and updates Redis state
- Complete event history is maintained for each job
- Services are decoupled and can scale independently

## Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Redis
- RabbitMQ

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd get-my-subtitle

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

```bash
# Copy environment template
cp env.template .env

# Edit .env with your API keys and configuration
nano .env
```

### 3. Start Services with Docker Compose

```bash
# Start all services (Redis, RabbitMQ, and workers)
docker-compose up -d

# View logs
docker-compose logs -f
```

### 4. Verify Installation

```bash
# Check Makefile commands
make help

# Check Invoke tasks (if installed)
invoke --list
```

### 5. Start Services

**Option A: Full Docker Mode** (Production-like):
```bash
make up                 # Start all services in Docker
make logs               # View logs
```

**Option B: Hybrid Mode** (Recommended for Development):
```bash
# Terminal 1: Start infrastructure
make up-infra           # Start Redis & RabbitMQ in Docker

# Terminal 2: Start manager with hot reload
make dev-manager

# Terminal 3: Start downloader worker
make dev-downloader

# Terminal 4: Start translator worker
make dev-translator
```

## Development Automation

This project includes both Makefile and Python Invoke tasks to streamline development workflows.

### Using Makefile (Recommended for Quick Operations)

View all available commands:
```bash
make help
```

#### Quick Setup
```bash
make setup              # Complete project setup (venv, deps, .env)
make install            # Install dependencies only
```

#### Docker Operations
```bash
make build              # Build all Docker images
make up                 # Start all services (full Docker mode)
make up-infra           # Start only Redis & RabbitMQ (hybrid mode)
make down               # Stop all services
make logs               # Follow logs from all services
```

#### Development Workflows

**Full Docker Mode** (production-like environment):
```bash
make up                 # Start all services in Docker
make logs               # View logs
```

**Hybrid Mode** (fast development with hot reload):
```bash
make up-infra           # Start Redis & RabbitMQ in Docker

# In separate terminals:
make dev-manager        # Run manager locally with hot reload
make dev-downloader     # Run downloader worker locally
make dev-translator     # Run translator worker locally
```

#### Testing
```bash
make test               # Run all tests
make test-unit          # Run unit tests only
make test-integration   # Run integration tests only
make test-cov           # Run tests with coverage report
make test-watch         # Run tests in watch mode
```

#### Code Quality
```bash
make lint               # Check code formatting
make format             # Auto-fix code formatting
make check              # Run lint + tests (pre-commit style)
```

#### Cleanup
```bash
make clean              # Remove Python cache files
make clean-docker       # Remove Docker containers and images
make clean-all          # Full cleanup
```

### Using Invoke (Advanced Workflows)

View all available tasks:
```bash
invoke --list
```

#### Advanced Docker Operations
```bash
invoke build-service manager        # Build specific service
invoke shell manager                # Open shell in container
invoke rebuild manager              # Force rebuild with no cache
```

#### Development Workflows
```bash
invoke dev                          # Start hybrid dev environment
invoke dev-full                     # Start full Docker environment
```

#### Health Checks
```bash
invoke health                       # Check health of all services
invoke wait-for-services            # Wait for services to be healthy
invoke wait-for-services --services="redis,rabbitmq"  # Wait for specific services
```

#### Database Operations
```bash
invoke redis-cli                    # Open Redis CLI
invoke redis-flush                  # Flush Redis database (with confirmation)
invoke rabbitmq-ui                  # Open RabbitMQ UI in browser
```

#### Testing & Quality
```bash
invoke test-e2e                     # Run end-to-end tests
invoke test-service manager         # Test specific service
invoke coverage-html                # Generate and open HTML coverage report
```

#### Utility Tasks
```bash
invoke logs-service manager         # View logs for specific service
invoke ps                           # Show status of all services
invoke top                          # Display container processes
```

### Common Development Workflows

#### First Time Setup
```bash
make setup              # Creates venv, installs deps, creates .env
# Edit .env with your API keys
make up                 # Start all services
```

#### Daily Development (Hybrid Mode)
```bash
make up-infra           # Start infrastructure
make dev-manager        # Terminal 1: API with hot reload
make dev-downloader     # Terminal 2: Downloader worker
make dev-translator     # Terminal 3: Translator worker
```

#### Before Committing
```bash
make check              # Runs lint + tests
# or separately:
make format             # Auto-fix formatting
make test-cov           # Run tests with coverage
```

#### Debugging
```bash
invoke shell manager    # Access container shell
invoke redis-cli        # Check Redis data
invoke rabbitmq-ui      # View RabbitMQ queues
invoke logs-service manager --no-follow  # View historical logs
```

#### Running Specific Tests
```bash
invoke test-service common          # Test common module
invoke test-service manager         # Test manager service
pytest tests/common/test_utils.py   # Test specific file
```

#### Clean Start
```bash
make clean-all          # Remove all caches and Docker resources
make build              # Rebuild images
make up                 # Start fresh
```

## Local Development Guide

This section provides comprehensive guidance for local development, including setup, debugging, and troubleshooting.

### First-Time Setup

#### 1. Prerequisites Checklist

Before starting, ensure you have:

- ✅ **Python 3.11+** installed
  ```bash
  python3 --version  # Should show 3.11 or higher
  ```

- ✅ **Docker and Docker Compose** installed
  ```bash
  docker --version
  docker-compose --version
  ```

- ✅ **Git** installed
  ```bash
  git --version
  ```

- ✅ **OpenSubtitles Account** (for subtitle downloads)
  - Sign up at [OpenSubtitles.org](https://www.opensubtitles.org/)
  - Get your username and password

- ✅ **OpenAI API Key** (for translations)
  - Get your API key from [OpenAI Platform](https://platform.openai.com/)

#### 2. Complete Project Setup

```bash
# Clone the repository
git clone <repository-url>
cd get-my-subtitle

# Run automated setup (creates venv, installs deps, creates .env)
make setup

# Edit .env with your API keys
nano .env  # or use your preferred editor
```

**Required Environment Variables:**
- `OPENSUBTITLES_USERNAME` - Your OpenSubtitles username
- `OPENSUBTITLES_PASSWORD` - Your OpenSubtitles password
- `OPENAI_API_KEY` - Your OpenAI API key (for translations)

#### 3. Verify Setup

```bash
# Check virtual environment is active
which python  # Should point to venv/bin/python

# Verify dependencies installed
pip list | grep -E "fastapi|redis|aio-pika"

# Check .env file exists
ls -la .env
```

### Development Modes

The project supports three development modes:

#### Full Docker Mode

**Use Case**: Production-like testing, CI/CD, or when you want everything containerized.

```bash
# Start all services
make up

# View logs
make logs

# Stop services
make down
```

**Pros:**
- Production-like environment
- Isolated from host system
- Easy to reset (just `make down` and `make up`)

**Cons:**
- Slower iteration (need to rebuild images for code changes)
- More resource intensive

#### Hybrid Mode (Recommended)

**Use Case**: Daily development with hot reload and fast iteration.

```bash
# Terminal 1: Start infrastructure only
make up-infra

# Terminal 2: Manager with hot reload
make dev-manager

# Terminal 3: Downloader worker
make dev-downloader

# Terminal 4: Translator worker
make dev-translator
```

**Pros:**
- Fast code changes (hot reload for manager)
- Direct access to logs
- Easy debugging with breakpoints
- Lower resource usage

**Cons:**
- Need multiple terminals
- Must manage processes manually

#### Local-Only Mode

**Use Case**: When you want to run everything locally without Docker.

```bash
# Install Redis and RabbitMQ locally (macOS)
brew install redis rabbitmq

# Start services
brew services start redis
brew services start rabbitmq

# Run services (same as hybrid mode)
make dev-manager
make dev-downloader
make dev-translator
```

**Pros:**
- No Docker overhead
- Native performance
- Direct service access

**Cons:**
- Requires local installation of Redis/RabbitMQ
- Platform-specific setup

### Environment Configuration

#### Key Environment Variables

**Infrastructure:**
```env
REDIS_URL=redis://localhost:6379
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
```

**OpenSubtitles:**
```env
OPENSUBTITLES_USERNAME=your_username
OPENSUBTITLES_PASSWORD=your_password
OPENSUBTITLES_USER_AGENT=get-my-subtitle v1.0
OPENSUBTITLES_MAX_RETRIES=3
```

**OpenAI (Translation):**
```env
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-5-nano
OPENAI_MAX_TOKENS=4096
OPENAI_TEMPERATURE=0.3
```

**File Storage:**
```env
SUBTITLE_STORAGE_PATH=./storage/subtitles
```

**Jellyfin Integration:**
```env
JELLYFIN_URL=http://localhost:8096
JELLYFIN_API_KEY=your_api_key
JELLYFIN_DEFAULT_SOURCE_LANGUAGE=en
JELLYFIN_DEFAULT_TARGET_LANGUAGE=he
JELLYFIN_AUTO_TRANSLATE=true
```

**Logging:**
```env
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

See `env.template` for all available options.

### Debugging Guide

#### Viewing Logs

**All Services:**
```bash
docker-compose logs -f
```

**Specific Service:**
```bash
docker-compose logs -f manager
docker-compose logs -f downloader
docker-compose logs -f translator
docker-compose logs -f consumer
```

**Local Development (Hybrid Mode):**
- Logs appear directly in terminal
- File logs in `logs/` directory: `logs/manager_YYYYMMDD.log`

#### Service Health Checks

```bash
# Manager API
curl http://localhost:8000/health

# RabbitMQ Management UI
open http://localhost:15672  # Login: guest/guest

# Redis
docker exec -it get-my-subtitle-redis-1 redis-cli ping
# or locally: redis-cli ping
```

#### Debugging with Invoke

```bash
# Check all service health
invoke health

# Access container shell
invoke shell manager

# View service logs
invoke logs-service manager

# Open Redis CLI
invoke redis-cli

# Open RabbitMQ UI
invoke rabbitmq-ui
```

#### Debugging Event Flows

**Check RabbitMQ Events:**
1. Open RabbitMQ UI: http://localhost:15672
2. Navigate to Exchanges → `subtitle.events`
3. Check message rates and routing

**Check Redis State:**
```bash
# Connect to Redis
invoke redis-cli

# List all jobs
KEYS job:*

# Get specific job
GET job:{job_id}

# Get event history
LRANGE job:events:{job_id} 0 -1
```

**Check Event History via API:**
```bash
curl http://localhost:8000/subtitles/{job_id}/events | jq
```

#### Common Debugging Scenarios

**Service Not Starting:**
```bash
# Check port conflicts
lsof -i :8000  # Manager
lsof -i :5672  # RabbitMQ
lsof -i :6379  # Redis

# Check Docker resources
docker system df
docker system prune -f
```

**Events Not Being Consumed:**
```bash
# Check consumer is running
docker-compose ps consumer

# Check consumer logs
docker-compose logs consumer

# Verify RabbitMQ connection
docker-compose logs consumer | grep -i "connection"

# Restart consumer
docker-compose restart consumer
```

**Jobs Stuck in Progress:**
```bash
# Check worker logs
docker-compose logs downloader
docker-compose logs translator

# Check RabbitMQ queues
open http://localhost:15672

# Restart workers
docker-compose restart downloader translator
```

### Development Tools

#### RabbitMQ Management UI

Access at http://localhost:15672 (guest/guest)

**Useful Features:**
- **Exchanges**: View `subtitle.events` exchange
- **Queues**: Monitor queue depths and message rates
- **Bindings**: Verify routing patterns
- **Publish Messages**: Manually publish test events

#### Redis CLI

```bash
# Connect
invoke redis-cli

# Common Commands
KEYS job:*              # List all jobs
GET job:{id}            # Get job data
LLEN job:events:{id}    # Count events
LRANGE job:events:{id} 0 -1  # Get all events
TTL job:{id}            # Check expiration
```

#### API Testing

**Interactive API Docs:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

**Command Line Testing:**
```bash
# Health check
curl http://localhost:8000/health

# Submit job
curl -X POST http://localhost:8000/subtitles/download \
  -H "Content-Type: application/json" \
  -d '{"video_url": "/path/to/video.mp4", "video_title": "Test", "language": "en"}'

# Check status
curl http://localhost:8000/subtitles/{job_id}/status
```

### Troubleshooting

#### Common Issues

**"Command not found" Errors:**
```bash
# Reinstall dependencies
make install

# Or recreate venv
rm -rf venv
make setup
```

**Tests Failing:**
```bash
# Clean cache
make clean

# Reinstall dependencies
make install

# Run with coverage to see details
make test-cov
```

**Docker Issues:**
```bash
# Clean Docker resources
make clean-docker

# Rebuild images
make build

# Start fresh
make up
```

**Virtual Environment Issues:**
```bash
# Remove and recreate
rm -rf venv
make setup
```

**Port Conflicts:**
```bash
# Find what's using the port
lsof -i :8000
lsof -i :5672
lsof -i :6379

# Stop conflicting services or change ports in docker-compose.yml
```

**Services Not Healthy:**
```bash
# Check service status
docker-compose ps

# View service logs
docker-compose logs [service_name]

# Restart specific service
docker-compose restart [service_name]

# Full restart
make down
make up
```

#### Diagnostic Commands

```bash
# Check all services
invoke health

# View all logs
docker-compose logs -f

# Check Docker resources
docker system df
docker stats

# Test Redis connection
redis-cli ping

# Test RabbitMQ connection
curl -u guest:guest http://localhost:15672/api/overview
```

## API Endpoints

Once running, the API will be available at `http://localhost:8000`

### Core Endpoints
- `GET /health` - Health check
- `POST /subtitles/download` - Request subtitle download from video
- `POST /subtitles/translate` - Enqueue subtitle file for translation by path
- `GET /subtitles/status/{job_id}` - Get job status with progress (lightweight)
- `GET /subtitles/{job_id}` - Get detailed subtitle job information (full details)
- `GET /subtitles` - List all subtitle requests

### Webhooks
- `POST /webhooks/jellyfin` - Jellyfin webhook for automatic subtitle processing

### Queue Management
- `GET /queue/status` - Get queue status and active workers

## Testing Guide

This section provides comprehensive testing guidance, from quick verification to full integration testing.

### Quick Test Start

Get up and running with testing in 5 minutes:

#### 1. Prerequisites Check
```bash
# Make sure Docker is running
docker ps

# Check you have the .env file
ls -la .env || cp env.template .env
```

#### 2. Start Services (30 seconds)
```bash
# Clean start
docker-compose down -v

# Build and start all services
docker-compose up --build -d

# Wait for services to be healthy (30-60 seconds)
sleep 30
```

#### 3. Verify Health (10 seconds)
```bash
# Quick health check
curl http://localhost:8000/health

# Expected: {"status": "ok"}
```

#### 4. Submit Test Job (5 seconds)
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

#### 5. Watch Progress (15-30 seconds)
```bash
# Replace {job_id} with actual job ID from step 4
watch -n 2 'curl -s http://localhost:8000/subtitles/{job_id}/status | jq'

# Expected progression:
# DOWNLOAD_QUEUED → DOWNLOAD_IN_PROGRESS → DONE
```

#### 6. Check Results (5 seconds)
```bash
# View job details and events
curl http://localhost:8000/subtitles/{job_id}/events | jq

# You should see:
# - Final status: DONE
# - Event history with all events
# - Complete timeline of what happened
```

### Running Tests

#### Unit Tests
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

#### Integration Tests

**Prerequisites:**
- Services must be running (RabbitMQ, Redis)
- Use `make up-infra` or `docker-compose up redis rabbitmq`

**Run Tests:**
```bash
# Run all integration tests
make test-integration

# Run with full Docker environment
make test-integration-full

# Run specific integration test
pytest tests/integration/test_scanner_manager_events.py -v

# Run with debug logging
pytest tests/integration/ --log-cli-level=DEBUG -v
```

**Integration Test Environment:**
- **CI (GitHub Actions)**: Services provided automatically
- **Local**: Start services with `make up-infra` or use `docker-compose.integration.yml`

#### Test Coverage
```bash
# Generate coverage report
make test-cov

# Open HTML report
open htmlcov/index.html

# Or use invoke
invoke coverage-html
```

### Manual Testing Guide

#### Test Scenarios

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

### Test Flow Diagrams

#### Complete System Architecture

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

#### Status Transitions

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

### Integration Testing

#### Environment Setup

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

#### Integration Test Categories

1. **Event Flow Tests** - End-to-end event-driven workflow
2. **Queue Publishing Tests** - RabbitMQ queue operations
3. **Full Publishing Flow Tests** - Combined task and event publishing

#### CI/CD Integration

Integration tests work seamlessly in CI/CD:
- **GitHub Actions**: Services provided automatically
- **Local**: Start services with `make up-infra` before running tests

### Test Checklist

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

### Performance Testing

#### Load Testing
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

#### Expected Performance

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

### Testing Tools

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
- [Logging Documentation](docs/LOGGING.md) - Logging configuration and usage
- Service-specific READMEs for service-specific testing

## Project Structure

```
get-my-subtitle/
├── manager/               # API + orchestrator service
│   ├── main.py           # FastAPI application
│   ├── orchestrator.py   # RabbitMQ orchestration
│   ├── event_consumer.py # Event consumer
│   ├── file_service.py   # File operations
│   ├── schemas.py        # Service-specific schemas
│   ├── README.md         # Service documentation
│   ├── Dockerfile        # Manager service container
│   └── requirements.txt  # Service dependencies
├── downloader/            # Subtitle fetch worker service
│   ├── worker.py         # Main worker process
│   ├── opensubtitles_client.py  # OpenSubtitles API client
│   ├── README.md         # Service documentation
│   ├── Dockerfile        # Downloader service container
│   └── requirements.txt  # Service dependencies
├── translator/            # Translation worker service
│   ├── worker.py         # Main worker process
│   ├── translation_service.py  # Translation logic
│   ├── checkpoint_manager.py   # Translation checkpoint management
│   ├── README.md         # Service documentation
│   ├── Dockerfile        # Translator service container
│   └── requirements.txt  # Service dependencies
├── scanner/              # Media detection service
│   ├── worker.py         # Main worker process
│   ├── scanner.py        # Media scanner
│   ├── websocket_client.py  # Jellyfin WebSocket client
│   ├── webhook_handler.py   # Webhook handler
│   ├── event_handler.py    # File system event handler
│   ├── README.md         # Service documentation
│   ├── Dockerfile        # Scanner service container
│   └── requirements.txt  # Service dependencies
├── consumer/             # Event consumer service
│   ├── worker.py         # Main worker process
│   ├── README.md         # Service documentation
│   ├── Dockerfile        # Consumer service container
│   └── requirements.txt  # Service dependencies
├── common/                # Shared code
│   ├── schemas.py        # Shared Pydantic models
│   ├── utils.py          # Utility functions
│   ├── config.py         # Configuration management
│   ├── redis_client.py   # Redis client
│   ├── event_publisher.py  # Event publishing
│   ├── logging_config.py  # Logging configuration
│   ├── retry_utils.py     # Retry utilities
│   └── subtitle_parser.py # Subtitle parsing
├── tests/                 # Test suite
│   ├── common/           # Common module tests
│   ├── manager/          # Manager service tests
│   ├── downloader/        # Downloader service tests
│   ├── translator/       # Translator service tests
│   ├── scanner/          # Scanner service tests
│   ├── consumer/         # Consumer service tests
│   ├── integration/     # Integration tests
│   └── conftest.py       # Pytest configuration
├── scripts/              # Utility scripts
│   ├── test_manual.sh    # Manual testing script
│   ├── ci_code_quality.sh  # CI code quality checks
│   ├── ci_run_tests.sh   # CI test execution
│   └── run_integration_tests.sh  # Integration test runner
├── docs/                 # Documentation
│   ├── INTEGRATION_TESTING.md  # Integration testing guide (legacy - see Testing Guide above)
│   └── LOGGING.md        # Logging configuration reference
├── docker-compose.yml     # Main service orchestration
├── docker-compose.integration.yml  # Integration test environment
├── Makefile              # Development automation
├── tasks.py              # Invoke tasks (advanced workflows)
├── requirements.txt      # Root Python dependencies
├── env.template          # Environment variables template
└── README.md             # This file
```

### Service Documentation

Each service has its own README with detailed documentation:
- [Manager Service](manager/README.md) - API and orchestration
- [Downloader Service](downloader/README.md) - Subtitle fetching
- [Translator Service](translator/README.md) - Subtitle translation
- [Scanner Service](scanner/README.md) - Media detection
- [Consumer Service](consumer/README.md) - Event processing

## Development

### Code Quality

The project includes automated code quality tools. Use the Makefile commands for consistency:

```bash
# Check formatting (without modifying files)
make lint

# Auto-fix formatting issues
make format

# Run all tests
make test

# Run tests with coverage report
make test-cov

# Run complete pre-commit check (lint + tests)
make check
```

For more granular control:

```bash
# Format code manually
black .
isort .

# Run tests with custom options
pytest -v
pytest --cov=common --cov=manager --cov-report=html
```

### Pre-commit Hooks

This project uses [pre-commit](https://pre-commit.com) hooks to automatically check code quality before each commit. The hooks ensure consistent code formatting and catch issues early.

#### Installation

After installing dependencies, set up pre-commit hooks:

```bash
# Install dependencies (includes pre-commit)
pip install -r requirements.txt

# Install git hooks
pre-commit install
```

#### Usage

Pre-commit hooks run automatically on `git commit`. They will:

1. **isort** - Sort and organize imports
2. **black** - Format code according to project style
3. **flake8** - Lint code for style and quality issues

Hooks will automatically fix issues when possible (isort, black) or report errors that need manual fixes (flake8).

#### Manual Execution

Run hooks manually on all files:

```bash
# Check all files
pre-commit run --all-files

# Run specific hook
pre-commit run black --all-files
pre-commit run isort --all-files
pre-commit run flake8 --all-files
```

#### Bypassing Hooks

If you need to bypass hooks (not recommended):

```bash
git commit --no-verify
```

#### Integration with Makefile

Pre-commit hooks complement the existing Makefile targets:

- `make format` - Manually format code (same as pre-commit black + isort)
- `make lint` - Manually check formatting (same as pre-commit checks)
- `make check` - Run lint + tests (pre-commit runs automatically on commit)

The hooks use the same configuration as CI/CD, ensuring consistency across local development and continuous integration.

### CI/CD

This project uses GitHub Actions for continuous integration and deployment:

#### Automated Workflows

1. **CI Pipeline** (`.github/workflows/ci.yml`)
   - ✅ Code formatting checks (Black, isort, Flake8)
   - ✅ Unit tests on Python 3.11 and 3.12 (matrix strategy)
   - ✅ Integration tests with Redis and RabbitMQ
   - ✅ Coverage reporting (60% minimum) with HTML and XML reports
   - ✅ Docker image build validation for all services
   - ✅ Security scanning (Bandit, Safety)
   - ✅ JUnit XML test result reporting
   - Runs on: Push to `main`/`develop`/`feat/*`, Pull Requests, Manual dispatch

2. **Lint Pipeline** (`.github/workflows/lint.yml`)
   - ✅ Black formatting validation
   - ✅ isort import sorting validation
   - ✅ Flake8 linting validation
   - ⚡ Fast feedback (~30-60 seconds)
   - ✅ Auto-comments on PRs with formatting issues
   - Runs on: Push and Pull Requests

3. **Dependency Updates** (Dependabot)
   - 🔄 Weekly automated dependency updates
   - 📦 Python packages, GitHub Actions, and Docker base images
   - 🔐 Automatic security vulnerability patches

#### Branch Protection

The `main` and `develop` branches are protected and require:
- ✅ All CI checks to pass
- ✅ Code review approval
- ✅ Up-to-date branches before merging
- ✅ Conversation resolution

#### Before Committing

Pre-commit hooks run automatically on `git commit`, but you can also run checks manually:

```bash
# Pre-commit hooks run automatically, or run manually:
pre-commit run --all-files

# Or use Makefile commands:
make check      # Run all checks (lint + tests)

# Or run individually:
make format     # Auto-fix formatting
make lint       # Check code style
make test-unit  # Run unit tests
make test-cov   # Check coverage
```

For more details, see [GitHub Actions Documentation](.github/workflows/README.md).

### Adding New Subtitle Sources

1. Create a new source class in `downloader/sources/`
2. Implement the required interface
3. Register the source in the downloader worker

### Adding New Translation Services

1. Create a new service class in `translator/services/`
2. Implement the required interface
3. Register the service in the translator worker

## Configuration

### Key Environment Variables

**Infrastructure:**
- `REDIS_URL`: Redis connection string (default: `redis://localhost:6379`)
- `RABBITMQ_URL`: RabbitMQ connection string (default: `amqp://guest:guest@localhost:5672/`)

**OpenSubtitles:**
- `OPENSUBTITLES_USERNAME`: OpenSubtitles username (required)
- `OPENSUBTITLES_PASSWORD`: OpenSubtitles password (required)
- `OPENSUBTITLES_USER_AGENT`: User agent string (default: `get-my-subtitle v1.0`)

**OpenAI (Translation):**
- `OPENAI_API_KEY`: OpenAI API key (required for translations)
- `OPENAI_MODEL`: Model to use (default: `gpt-5-nano`)
- `OPENAI_MAX_TOKENS`: Maximum tokens per request (default: `4096`)

**File Storage:**
- `SUBTITLE_STORAGE_PATH`: Path to store subtitle files (default: `./storage/subtitles`)

**Jellyfin Integration:**
- `JELLYFIN_URL`: Jellyfin server URL
- `JELLYFIN_API_KEY`: Jellyfin API key
- `JELLYFIN_DEFAULT_SOURCE_LANGUAGE`: Default source language (default: `en`)
- `JELLYFIN_DEFAULT_TARGET_LANGUAGE`: Default target language (optional)
- `JELLYFIN_AUTO_TRANSLATE`: Enable automatic translation (default: `true`)

**Logging:**
- `LOG_LEVEL`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) (default: `INFO`)

See `env.template` for all available configuration options with descriptions.

## Additional Documentation

- [Logging Documentation](docs/LOGGING.md) - Comprehensive logging configuration and usage guide
- [Service READMEs](#service-documentation) - Detailed documentation for each service
- [Testing Guide](#testing-guide) - Complete testing documentation
- [Local Development Guide](#local-development-guide) - Setup and debugging guide

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run `make check` to ensure code quality
6. Submit a pull request

### Development Workflow

```bash
# Before making changes
git checkout -b feature/your-feature-name

# Make your changes
# ... edit files ...

# Run tests and linting
make check

# Commit your changes
git commit -m "Add your feature"

# Push and create PR
git push origin feature/your-feature-name
```

## License

MIT License
