# Get My Subtitle

[![CI](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/ci.yml/badge.svg)](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/ci.yml)
[![Lint](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/lint.yml/badge.svg)](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/lint.yml)
[![codecov](https://codecov.io/gh/yairabramovitch/get-my-subtitle/branch/main/graph/badge.svg)](https://codecov.io/gh/yairabramovitch/get-my-subtitle)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A microservices-based subtitle management system that automatically fetches, translates, and manages subtitles for your video library. Perfect for home media servers like Jellyfin, Plex, or standalone video collections.

## Purpose

**Get My Subtitle** solves the problem of missing or untranslated subtitles in your video library by automatically detecting, fetching, translating, and managing subtitles for your media collection.

## Table of Contents

- [Purpose](#purpose)
- [Recent Updates](#recent-updates)
- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
  - [Monitoring & Utilities](#monitoring--utilities)
  - [API Endpoints Overview](#api-endpoints-overview)
  - [Running on Homelab/Production](#running-on-homelab-production)
  - [Performance Optimization](#performance-optimization)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## Recent Updates

**Performance & Reliability Improvements:**
- ✨ **Parallel Translation Processing**: Process 3-6 translation chunks simultaneously (5-10x faster)
- 🚀 **Optimized Batch Sizes**: Increased default batch size from 50 to 100 segments for GPT-4o-mini
- 🔄 **Enhanced Retry Logic**: Improved error handling with exponential backoff for API failures
- 📊 **Monitoring Scripts**: Added real-time monitoring tools (`monitor-realtime.sh`, `monitor-workers.sh`)
- 🛠️ **Development Tools**: Comprehensive Makefile with 30+ commands for development tasks
- 🔧 **Pre-commit Hooks**: Automated code quality checks with black, isort, and flake8
- 📝 **Centralized Language Config**: Simplified language configuration with `SUBTITLE_DESIRED_LANGUAGE` and `SUBTITLE_FALLBACK_LANGUAGE`
- 🏥 **Health Checks**: Docker health checks for all services ensure reliability

## Features

### Core Functionality
- **Automatic Media Detection**: Detects new media files via multiple methods:
  - Jellyfin WebSocket real-time notifications
  - Jellyfin webhook integration
  - File system monitoring with recursive directory watching
  - Manual scan API endpoint
- **Subtitle Download**: Fetches subtitles from OpenSubtitles with intelligent search:
  - Hash-based matching for exact file identification
  - Query-based fallback search by title
  - Automatic language preference handling
- **AI-Powered Translation**: Translates subtitles using OpenAI models:
  - Supports GPT-4o-mini (recommended), GPT-4o, GPT-4, and other OpenAI models
  - **Parallel Processing**: Processes 3-6 translation chunks simultaneously (5-10x speedup)
    - Automatic model-based parallel request selection (3 for GPT-4o-mini, 6 for higher tier models)
    - Semaphore-based rate limiting to respect API limits
    - Out-of-order completion handling with automatic result sorting
  - Optimized batch processing (100 segments per chunk by default, configurable up to 200)
  - Token-aware chunking for large subtitle files
  - Timing and formatting preservation (HTML tags, line breaks, etc.)
  - **Checkpoint/Resume System**: Resume interrupted translations from saved checkpoints
    - Checkpoints saved after each parallel batch completion
    - Automatic cleanup after successful completion  
    - Configurable via `CHECKPOINT_ENABLED` and `CHECKPOINT_CLEANUP_ON_SUCCESS`
  - Intelligent error handling with retry mechanism for parsing failures
  - Tolerance for minor parsing issues (1 missing translation uses original text)
  - Accurate missing segment identification using parsed segment numbers
- **REST API**: Complete programmatic access:
  - Request subtitle downloads for videos
  - Upload and translate subtitle files directly
  - Track job status and progress with percentage completion
  - View complete event history for audit trails
  - List all subtitle jobs
  - Queue status monitoring
  - Health check endpoints for service monitoring

### Advanced Features
- **Event-Driven Architecture**: Decoupled microservices with RabbitMQ message broker
- **Parallel Translation Processing**: Process multiple translation chunks simultaneously with semaphore-based rate limiting (3-6 concurrent requests based on API tier)
- **Checkpoint System**: Resume interrupted translations from saved checkpoints
- **Duplicate Prevention**: Prevents processing the same media file multiple times
- **Retry Logic**: Exponential backoff retry for API failures (OpenAI and OpenSubtitles)
  - Automatic retry for transient parsing errors (TranslationCountMismatchError)
  - Custom exception handling for translation count mismatches with detailed context
  - Retry mechanism recognizes parsing failures as transient errors
  - Graceful handling of partial failures in parallel processing with detailed error reporting
- **Real-Time Status Updates**: Redis-based job tracking with event history
- **Jellyfin Integration**: Automatic subtitle processing for Jellyfin media library
- **Configurable Batch Sizes**: Optimize translation performance based on model capabilities
- **Configurable Parallel Requests**: Adjust concurrent translation requests based on API tier (3 for GPT-4o-mini, 6 for higher tier)
- **Health Monitoring**: Health check endpoints for all services
- **Comprehensive Logging**: Structured logging with file and console output

The system uses an event-driven microservices architecture, making it scalable, maintainable, and easy to extend with new subtitle sources or translation services.

## Architecture

This project consists of multiple microservices working together:

- **Manager**: FastAPI-based API server and orchestrator
- **Downloader**: Worker service for fetching subtitles from various sources
- **Translator**: Worker service for translating subtitles using AI
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

## Quick Start

### Prerequisites

- Docker and Docker Compose
- OpenSubtitles account (for subtitle downloads)
- OpenAI API key (optional, only needed for translations)

### Setup Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yairabramovitch/get-my-subtitle.git
   cd get-my-subtitle
   ```

2. **Create `.env` file:**
   ```bash
   cp .example.env .env
   ```

3. **Configure `.env` with minimal required variables:**
   
   **For download-only mode (no translation):**
   ```env
   OPENSUBTITLES_USERNAME=your_username
   OPENSUBTITLES_PASSWORD=your_password
   ```
   
   **For full functionality (download + translation):**
   ```env
   OPENSUBTITLES_USERNAME=your_username
   OPENSUBTITLES_PASSWORD=your_password
   OPENAI_API_KEY=sk-your-openai-api-key-here
   OPENAI_MODEL=gpt-4o-mini
   
   # Optional: Configure parallel translation processing (speeds up translation 5-10x)
   TRANSLATION_PARALLEL_REQUESTS=3              # For GPT-4o-mini (low rate limit)
   TRANSLATION_PARALLEL_REQUESTS_HIGH_TIER=6    # For GPT-4o, GPT-4 (higher tier)
   
   # Optional: Configure checkpoint system for long translations
   CHECKPOINT_ENABLED=true                      # Enable resume on crash
   CHECKPOINT_CLEANUP_ON_SUCCESS=true           # Auto-cleanup checkpoints
   ```

4. **Start services:**
   
   **Full stack (all services including translator):**
   ```bash
   docker-compose up --build -d
   ```
   
   **Without translator service (download-only):**
   ```bash
   docker-compose up --build -d manager downloader consumer scanner
   ```
   
   Or comment out the `translator:` section in `docker-compose.yml` and run:
   ```bash
   docker-compose up --build -d
   ```

5. **Verify installation:**
   ```bash
   curl http://localhost:8000/health
   # Expected: {"status": "ok"}
   ```

6. **Access the API:**
   - API: http://localhost:8000
   - Interactive Docs (Swagger): http://localhost:8000/docs
   - Alternative Docs (ReDoc): http://localhost:8000/redoc
   - RabbitMQ Management UI: http://localhost:15672 (guest/guest)
   - Scanner Webhook Endpoint: http://localhost:8001

### Monitoring & Utilities

The project includes several utility scripts for monitoring, debugging, and manual operations:

#### Monitoring Scripts

**Real-time monitoring (updates every 3 seconds):**
```bash
./monitor-realtime.sh
```

**Comprehensive system status:**
```bash
./monitor-workers.sh          # Continuous monitoring (refreshes every 5 seconds)
./monitor-workers.sh --once   # Run once and exit
```

These scripts provide:
- Docker service status
- Infrastructure health (Redis, RabbitMQ, APIs)
- Active worker processes
- Queue status and message counts
- Recent logs from all services
- Translation flow tracking

#### Utility Scripts

**Run individual workers locally (for debugging):**
```bash
./run-worker.sh <worker_name>
```
Available workers: `manager`, `downloader`, `translator`, `consumer`, `scanner`

**Trigger manual media library scan:**
```bash
./initiate-scan.sh
```

This sends a scan request to the Scanner service to process all media files in the configured directory.

### API Endpoints Overview

The Manager service provides a comprehensive REST API:

**Subtitle Management:**
- `POST /subtitles/download` - Request subtitle download for a video
- `POST /subtitles/translate` - Upload and translate a subtitle file directly
- `GET /subtitles/{job_id}` - Get detailed job information
- `GET /subtitles/status/{job_id}` - Get job status with progress percentage (0-100%)
- `GET /subtitles/{job_id}/events` - Get complete event history for a job (audit trail)
- `GET /subtitles` - List all subtitle jobs

**Monitoring & Control:**
- `GET /health` - Health check endpoint (includes Redis connectivity)
- `GET /health/consumer` - Event consumer health status (SUBTITLE_REQUESTED events)
- `GET /queue/status` - Get processing queue status (download and translation queues)
- `POST /scan` - Trigger manual media library scan (proxies to Scanner service)
- `POST /webhooks/jellyfin` - Jellyfin webhook endpoint for automatic processing
- `GET /` - API information and version

See the [Manager Service documentation](src/manager/README.md) for detailed API documentation.

### Running on Homelab/Production

For production deployment on a homelab server:

```bash
# On your server
git clone https://github.com/yairabramovitch/get-my-subtitle.git
cd get-my-subtitle
cp .example.env .env
# Edit .env with your configuration

# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Monitor system health
./monitor-workers.sh --once
```

**Production recommendations:**
- Set `SUBTITLE_STORAGE_PATH` to a persistent volume path
- Configure `JELLYFIN_URL` and `JELLYFIN_API_KEY` if using Jellyfin integration
- Set up reverse proxy (nginx/traefik) for the Manager API
- Configure `TRANSLATION_PARALLEL_REQUESTS` based on your OpenAI API tier for optimal performance
- Use monitoring scripts (`monitor-workers.sh`, `monitor-realtime.sh`) to track system health
- Set up log rotation for production environments
- See [Configuration Guide](docs/CONFIGURATION.md) for detailed production setup

### Performance Optimization

The system has been optimized for speed and reliability:

**Translation Speed:**
- **Parallel Processing**: Process multiple translation chunks simultaneously for 5-10x speedup
  - Default: 3 concurrent requests for GPT-4o-mini (respects rate limits)
  - 6 concurrent requests for higher tier models (GPT-4o, GPT-4)
  - Automatically selected based on model via `get_translation_parallel_requests()`
  - Configure via `TRANSLATION_PARALLEL_REQUESTS` and `TRANSLATION_PARALLEL_REQUESTS_HIGH_TIER`
  - Semaphore-based rate limiting prevents exceeding API limits
  - Out-of-order completion handling with automatic result sorting

- **Optimized Batch Sizes**: Tune batch sizes for optimal performance
  - Default: 100 segments per chunk for GPT-4o-mini (recommended)
  - Configure via `TRANSLATION_MAX_SEGMENTS_PER_CHUNK`
  - Larger batches = fewer API calls but higher token usage
  - Recommended: 100-200 for GPT-4o-mini, up to 300-400 for higher tier models
  - Recent optimization: Increased from 50 to 100 for GPT-4o-mini (faster, no errors)

- **Checkpoint System**: Resume interrupted translations without losing progress
  - Checkpoints saved after each parallel batch completion
  - Automatic cleanup after successful completion
  - Configurable via `CHECKPOINT_ENABLED` and `CHECKPOINT_CLEANUP_ON_SUCCESS`

**Reliability Features:**
- **Retry Logic**: Exponential backoff for both OpenAI and OpenSubtitles APIs
- **Error Recovery**: Graceful handling of partial failures in parallel processing
- **Health Checks**: Automatic service health monitoring via Docker health checks
- **Duplicate Prevention**: Prevents processing the same file multiple times
- **Event-Driven Architecture**: Decoupled services ensure system resilience

## Documentation

### Main Guides

- **[Configuration Guide](docs/CONFIGURATION.md)** - Complete environment variable and Docker Compose configuration reference
- **[Development Guide](docs/DEVELOPMENT.md)** - Local development setup, debugging, and workflows
- **[Testing Guide](docs/TESTING.md)** - Testing documentation and test execution

### Service Documentation

Each service has detailed documentation:

- **[Manager Service](src/manager/README.md)** - API and orchestration service
- **[Downloader Service](src/downloader/README.md)** - Subtitle fetching service
- **[Translator Service](src/translator/README.md)** - Subtitle translation service
- **[Scanner Service](src/scanner/README.md)** - Media detection service
- **[Consumer Service](src/consumer/README.md)** - Event processing service

### Additional Documentation

- **[Logging Documentation](docs/LOGGING.md)** - Logging configuration and usage guide
- **[Local Development Guide](LOCAL_DEVELOPMENT.md)** - Running workers locally for debugging
- **[CI/CD Scripts](scripts/README.md)** - Continuous integration and deployment scripts
- **[Integration Tests](tests/integration/README.md)** - Integration testing documentation

## Contributing

### Development Workflow

1. **Fork the repository**
2. **Clone and setup:**
   ```bash
   git clone https://github.com/your-username/get-my-subtitle.git
   cd get-my-subtitle
   make setup  # Creates venv, installs dependencies, creates .env
   ```

3. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

4. **Make your changes and test:**
   ```bash
   make format      # Auto-format code (black + isort)
   make lint        # Check code formatting
   make test        # Run all tests
   make check       # Run lint + tests together
   ```

5. **Pre-commit hooks (recommended):**
   ```bash
   pip install pre-commit
   pre-commit install
   ```
   This automatically runs `black`, `isort`, and `flake8` before each commit.

6. **Submit a pull request**

### Development Commands

The project includes a comprehensive Makefile for development tasks:

**Setup & Environment:**
- `make setup` - Complete project setup (venv, dependencies, .env)
- `make install` - Install Python dependencies only

**Docker Operations:**
- `make up` - Start all services in Docker
- `make up-infra` - Start only Redis & RabbitMQ (for hybrid development)
- `make down` - Stop all services
- `make logs` - Follow logs from all services

**Hybrid Mode (Run workers locally):**
- `make dev-manager` - Run manager locally with hot reload
- `make dev-downloader` - Run downloader worker locally
- `make dev-translator` - Run translator worker locally

**Testing:**
- `make test` - Run all tests
- `make test-unit` - Run unit tests only
- `make test-integration` - Run integration tests (requires services running)
- `make test-integration-full` - Run integration tests with full Docker environment
- `make test-e2e` - Run end-to-end tests
- `make test-cov` - Run tests with coverage report
- `make test-watch` - Run tests in watch mode

**Code Quality:**
- `make format` - Auto-format code with black and isort
- `make lint` - Check code formatting
- `make check` - Run lint + tests (pre-commit style check)

**Cleanup:**
- `make clean` - Remove Python cache files
- `make clean-docker` - Remove Docker containers and volumes
- `make clean-all` - Full cleanup (Python + Docker)

For detailed development instructions, see the [Development Guide](docs/DEVELOPMENT.md).

## License

MIT License
