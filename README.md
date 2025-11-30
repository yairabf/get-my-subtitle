# Get My Subtitle

[![CI](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/ci.yml/badge.svg)](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/ci.yml)
[![Lint](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/lint.yml/badge.svg)](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/lint.yml)
[![codecov](https://codecov.io/gh/yairabramovitch/get-my-subtitle/branch/main/graph/badge.svg)](https://codecov.io/gh/yairabramovitch/get-my-subtitle)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A microservices-based subtitle management system that automatically fetches, translates, and manages subtitles for your video library. Perfect for home media servers like Jellyfin, Plex, or standalone video collections.

## Purpose

**Get My Subtitle** solves the problem of missing or untranslated subtitles in your video library by automatically detecting, fetching, translating, and managing subtitles for your media collection.

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
  - Supports GPT-4o-mini (recommended) and other OpenAI models
  - Optimized batch processing (100-200 segments per request)
  - Token-aware chunking for large subtitle files
  - Timing and formatting preservation
  - Checkpoint/resume support for long translations
- **REST API**: Complete programmatic access:
  - Request subtitle downloads
  - Upload and translate subtitle files directly
  - Track job status and progress
  - View complete event history
  - Download translated subtitle files
  - Queue status monitoring

### Advanced Features
- **Event-Driven Architecture**: Decoupled microservices with RabbitMQ message broker
- **Checkpoint System**: Resume interrupted translations from saved checkpoints
- **Duplicate Prevention**: Prevents processing the same media file multiple times
- **Retry Logic**: Exponential backoff retry for API failures (OpenAI and OpenSubtitles)
- **Real-Time Status Updates**: Redis-based job tracking with event history
- **Jellyfin Integration**: Automatic subtitle processing for Jellyfin media library
- **Configurable Batch Sizes**: Optimize translation performance based on model capabilities
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
   git clone <repository-url>
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

### API Endpoints Overview

The Manager service provides a comprehensive REST API:

**Subtitle Management:**
- `POST /subtitles/download` - Request subtitle download for a video
- `POST /subtitles/translate` - Upload and translate a subtitle file directly
- `GET /subtitles/{job_id}` - Get detailed job information
- `GET /subtitles/status/{job_id}` - Get job status with progress percentage
- `GET /subtitles/{job_id}/events` - Get complete event history for a job
- `GET /subtitles` - List all subtitle jobs
- `GET /subtitles/download/{job_id}` - Download subtitle file

**Monitoring & Control:**
- `GET /health` - Health check endpoint
- `GET /health/consumer` - Event consumer health status
- `GET /queue/status` - Get processing queue status
- `POST /scan` - Trigger manual media library scan
- `POST /webhooks/jellyfin` - Jellyfin webhook endpoint

See the [Manager Service documentation](src/manager/README.md) for detailed API documentation.

### Running on Homelab/Production

For production deployment on a homelab server:

```bash
# On your server
git clone <repository-url>
cd get-my-subtitle
cp .example.env .env
# Edit .env with your configuration

# Start services
docker-compose up -d

# View logs
docker-compose logs -f
```

**Production recommendations:**
- Set `SUBTITLE_STORAGE_PATH` to a persistent volume path
- Configure `JELLYFIN_URL` and `JELLYFIN_API_KEY` if using Jellyfin integration
- Set up reverse proxy (nginx/traefik) for the Manager API
- See [Configuration Guide](docs/CONFIGURATION.md) for detailed production setup

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

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run `make check` to ensure code quality
6. Submit a pull request

For detailed development instructions, see the [Development Guide](docs/DEVELOPMENT.md).

## License

MIT License
