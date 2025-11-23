# Development Guide

This guide provides comprehensive information for local development, including setup, debugging, and troubleshooting.

> **📖 See Also**: [Main README](../README.md) for project overview and deployment options.

## Table of Contents

- [First-Time Setup](#first-time-setup)
- [Development Modes](#development-modes)
- [Development Automation](#development-automation)
- [Environment Configuration](#environment-configuration)
- [Debugging Guide](#debugging-guide)
- [Development Tools](#development-tools)
- [Troubleshooting](#troubleshooting)

## First-Time Setup

### Prerequisites Checklist

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

### Complete Project Setup

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

### Verify Setup

```bash
# Check virtual environment is active
which python  # Should point to venv/bin/python

# Verify dependencies installed
pip list | grep -E "fastapi|redis|aio-pika"

# Check .env file exists
ls -la .env
```

## Development Modes

The project supports three development modes:

### Full Docker Mode

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

### Hybrid Mode (Recommended)

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

### Local-Only Mode

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

## Environment Configuration

### Key Environment Variables

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

## Debugging Guide

### Viewing Logs

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

### Service Health Checks

```bash
# Manager API
curl http://localhost:8000/health

# RabbitMQ Management UI
open http://localhost:15672  # Login: guest/guest

# Redis
docker exec -it get-my-subtitle-redis-1 redis-cli ping
# or locally: redis-cli ping
```

### Debugging with Invoke

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

### Debugging Event Flows

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

### Common Debugging Scenarios

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

## Development Tools

### RabbitMQ Management UI

Access at http://localhost:15672 (guest/guest)

**Useful Features:**
- **Exchanges**: View `subtitle.events` exchange
- **Queues**: Monitor queue depths and message rates
- **Bindings**: Verify routing patterns
- **Publish Messages**: Manually publish test events

### Redis CLI

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

### API Testing

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

## Troubleshooting

### Common Issues

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

### Diagnostic Commands

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

## Code Quality

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

## Adding New Features

### Adding New Subtitle Sources

1. Create a new source class in `downloader/sources/`
2. Implement the required interface
3. Register the source in the downloader worker

### Adding New Translation Services

1. Create a new service class in `translator/services/`
2. Implement the required interface
3. Register the service in the translator worker



