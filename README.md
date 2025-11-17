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

2. **Create minimal `.env` file:**
   ```bash
   cp env.template .env
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
   - Interactive Docs: http://localhost:8000/docs
   - RabbitMQ UI: http://localhost:15672 (guest/guest)

### Running on Homelab/Production

For production deployment on a homelab server:

```bash
# On your server
git clone <repository-url>
cd get-my-subtitle
cp env.template .env
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
- See [Configuration Guide](CONFIGURATION.md) for detailed production setup

## Documentation

### Main Guides

- **[Configuration Guide](CONFIGURATION.md)** - Complete environment variable and Docker Compose configuration reference
- **[Development Guide](DEVELOPMENT.md)** - Local development setup, debugging, and workflows
- **[Testing Guide](TESTING.md)** - Testing documentation and test execution

### Service Documentation

Each service has detailed documentation:

- **[Manager Service](src/manager/README.md)** - API and orchestration service
- **[Downloader Service](src/downloader/README.md)** - Subtitle fetching service
- **[Translator Service](src/translator/README.md)** - Subtitle translation service
- **[Scanner Service](src/scanner/README.md)** - Media detection service
- **[Consumer Service](src/consumer/README.md)** - Event processing service

### Additional Documentation

- **[Logging Documentation](docs/LOGGING.md)** - Logging configuration and usage guide
- **[CI/CD Scripts](scripts/README.md)** - Continuous integration and deployment scripts
- **[Integration Tests](tests/integration/README.md)** - Integration testing documentation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run `make check` to ensure code quality
6. Submit a pull request

For detailed development instructions, see the [Development Guide](DEVELOPMENT.md).

## License

MIT License
