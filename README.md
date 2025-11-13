# Get My Subtitle

[![CI](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/ci.yml/badge.svg)](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/ci.yml)
[![Lint](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/lint.yml/badge.svg)](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/lint.yml)
[![codecov](https://codecov.io/gh/yairabramovitch/get-my-subtitle/branch/main/graph/badge.svg)](https://codecov.io/gh/yairabramovitch/get-my-subtitle)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A microservices-based subtitle management system that automatically fetches, translates, and manages subtitles for your video library. Perfect for home media servers like Jellyfin, Plex, or standalone video collections.

## Purpose

**Get My Subtitle** solves the problem of missing or untranslated subtitles in your video library by:

- **Automatically detecting** new media files via Jellyfin webhooks, WebSocket events, or file system monitoring
- **Fetching subtitles** from multiple sources (OpenSubtitles, etc.) when available
- **Translating subtitles** using AI (OpenAI) when subtitles aren't available in your preferred language
- **Managing subtitle files** with automatic organization and metadata tracking
- **Providing a REST API** for programmatic subtitle requests and status tracking

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

## Deployment Options

The system can be deployed in several ways depending on your use case:

### 1. Local Docker (Recommended for Quick Start)

**Best for**: Quick testing, development, or small personal setups

Run everything in Docker containers on your local machine:

```bash
# Clone and setup
git clone <repository-url>
cd get-my-subtitle
make setup

# Configure environment
cp env.template .env
# Edit .env with your API keys

# Start all services
make up

# View logs
make logs
```

**Pros:**
- Easy setup - everything containerized
- Isolated from host system
- Production-like environment
- Easy to reset

**Cons:**
- Requires Docker and Docker Compose
- More resource intensive than local-only

### 2. Homelab / Production Deployment

**Best for**: Running on a home server, NAS, or production environment

Deploy using Docker Compose on your homelab server:

```bash
# On your server
git clone <repository-url>
cd get-my-subtitle
cp env.template .env
# Configure .env for your environment

# Start services
docker-compose up -d

# View logs
docker-compose logs -f
```

**Configuration for Homelab:**
- Set `JELLYFIN_URL` to your Jellyfin server URL
- Configure `SUBTITLE_STORAGE_PATH` to a persistent volume
- Set up reverse proxy (nginx/traefik) for the Manager API
- Configure automatic restarts with Docker restart policies

**Pros:**
- Production-ready
- Persistent storage
- Can integrate with existing homelab infrastructure
- Easy to manage with Docker Compose

**Cons:**
- Requires server with Docker
- Need to manage volumes and networking

### 3. Hybrid Development Mode

**Best for**: Active development with hot reload

Run infrastructure (Redis, RabbitMQ) in Docker, but run application services locally:

```bash
# Terminal 1: Start infrastructure
make up-infra

# Terminal 2: Manager with hot reload
make dev-manager

# Terminal 3: Downloader worker
make dev-downloader

# Terminal 4: Translator worker
make dev-translator
```

**Pros:**
- Fast code changes (hot reload)
- Direct access to logs
- Easy debugging with breakpoints
- Lower resource usage

**Cons:**
- Need multiple terminals
- Must manage processes manually

### 4. Local-Only Mode

**Best for**: Development without Docker overhead

Run everything locally (requires local Redis and RabbitMQ installation):

```bash
# Install Redis and RabbitMQ locally (macOS)
brew install redis rabbitmq

# Start services
brew services start redis
brew services start rabbitmq

# Run application services
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

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose (for Docker deployments)
- OpenSubtitles account (for subtitle downloads)
- OpenAI API key (for translations)

### Setup Steps

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd get-my-subtitle
   ```

2. **Run automated setup:**
   ```bash
   make setup  # Creates venv, installs deps, creates .env
   ```

3. **Configure environment:**
   ```bash
   # Edit .env with your API keys
   nano .env
   ```
   
   Required variables:
   - `OPENSUBTITLES_USERNAME` - Your OpenSubtitles username
   - `OPENSUBTITLES_PASSWORD` - Your OpenSubtitles password
   - `OPENAI_API_KEY` - Your OpenAI API key

4. **Start services:**
   ```bash
   # Option A: Full Docker (recommended for first-time users)
   make up
   
   # Option B: Hybrid mode (for development)
   make up-infra
   make dev-manager  # In separate terminal
   ```

5. **Verify installation:**
   ```bash
   curl http://localhost:8000/health
   # Expected: {"status": "ok"}
   ```

6. **Access the API:**
   - API: http://localhost:8000
   - Interactive Docs: http://localhost:8000/docs
   - RabbitMQ UI: http://localhost:15672 (guest/guest)

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

## Configuration

For complete configuration details, see the **[Configuration Guide](CONFIGURATION.md)**.

### Quick Start Configuration

**Mandatory Variables** (must be set):
- `OPENSUBTITLES_USERNAME` - Your OpenSubtitles username
- `OPENSUBTITLES_PASSWORD` - Your OpenSubtitles password
- `OPENAI_API_KEY` - Your OpenAI API key (required for translations)

**Quick Setup:**
```bash
cp env.template .env
# Edit .env with your credentials
```

**Optional but Recommended:**
- `JELLYFIN_URL` - If using Jellyfin integration
- `JELLYFIN_API_KEY` - If using Jellyfin integration
- `JELLYFIN_DEFAULT_TARGET_LANGUAGE` - Target language for translations (e.g., "he")

See the [Configuration Guide](CONFIGURATION.md) for:
- Complete list of all environment variables (mandatory vs optional)
- Docker Compose configuration options
- Configuration examples for different use cases (minimal, production, development)
- Volume, port, and network configuration
- Production deployment examples

## Documentation

### Main Guides

- **[Configuration Guide](CONFIGURATION.md)** - Complete configuration reference including:
  - Environment variables (.env) - mandatory vs optional
  - Docker Compose configuration
  - Configuration by use case (minimal, full, production, development)
  - Volume, port, and network configuration
  - Production deployment examples
  - Troubleshooting configuration issues

- **[Development Guide](DEVELOPMENT.md)** - Comprehensive local development guide including:
  - First-time setup and prerequisites
  - Development modes (Full Docker, Hybrid, Local-only)
  - Development automation (Makefile, Invoke)
  - Environment configuration
  - Debugging guide
  - Development tools
  - Troubleshooting

- **[Testing Guide](TESTING.md)** - Complete testing documentation including:
  - Quick test start
  - Running unit and integration tests
  - Manual testing scenarios
  - Test flow diagrams
  - Integration testing setup
  - Performance testing
  - Testing tools

### Additional Documentation

- [Logging Documentation](docs/LOGGING.md) - Comprehensive logging configuration and usage guide
- [Service READMEs](#service-documentation) - Detailed documentation for each service

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
│   └── LOGGING.md        # Logging configuration reference
├── docker-compose.yml     # Main service orchestration
├── docker-compose.integration.yml  # Integration test environment
├── Makefile              # Development automation
├── tasks.py              # Invoke tasks (advanced workflows)
├── requirements.txt      # Root Python dependencies
├── env.template          # Environment variables template
├── DEVELOPMENT.md        # Development guide
├── TESTING.md            # Testing guide
└── README.md             # This file
```

### Service Documentation

Each service has its own README with detailed documentation:
- [Manager Service](manager/README.md) - API and orchestration
- [Downloader Service](downloader/README.md) - Subtitle fetching
- [Translator Service](translator/README.md) - Subtitle translation
- [Scanner Service](scanner/README.md) - Media detection
- [Consumer Service](consumer/README.md) - Event processing

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

For detailed development instructions, see the [Development Guide](DEVELOPMENT.md).

## CI/CD

This project uses GitHub Actions for continuous integration:

- **CI Pipeline**: Code formatting, unit tests, integration tests, coverage reporting, Docker builds, security scanning
- **Lint Pipeline**: Fast formatting and linting checks
- **Dependabot**: Automated dependency updates

For more details, see [GitHub Actions Documentation](.github/workflows/README.md).

## License

MIT License
