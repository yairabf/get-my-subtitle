# Get My Subtitle

A microservices-based subtitle management system that fetches, translates, and manages subtitles for videos.

## Architecture

This project consists of three main services:

- **Manager**: FastAPI-based API server and orchestrator
- **Downloader**: Worker service for fetching subtitles from various sources
- **Translator**: Worker service for translating subtitles
- **Common**: Shared schemas, utilities, and configuration

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

### 4. Development Mode

For local development without Docker:

```bash
# Terminal 1: Start Redis and RabbitMQ
docker-compose up redis rabbitmq

# Terminal 2: Start the manager API
cd manager
uvicorn main:app --reload

# Terminal 3: Start downloader worker
cd downloader
python worker.py

# Terminal 4: Start translator worker
cd translator
python worker.py
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

## API Endpoints

Once running, the API will be available at `http://localhost:8000`

- `GET /health` - Health check
- `POST /subtitles/request` - Request subtitle processing
- `GET /subtitles/{id}` - Get subtitle status
- `GET /subtitles/{id}/download` - Download processed subtitles

## Project Structure

```
get-my-subtitle/
├── manager/               # API + orchestrator
│   ├── main.py           # FastAPI application
│   ├── models.py         # Pydantic models
│   ├── routes.py         # API routes
│   └── Dockerfile        # Manager service container
├── downloader/            # Subtitle fetch worker
│   ├── worker.py         # Main worker process
│   ├── sources/          # Subtitle source implementations
│   └── Dockerfile        # Downloader service container
├── translator/            # Translation worker
│   ├── worker.py         # Main worker process
│   ├── services/         # Translation service implementations
│   └── Dockerfile        # Translator service container
├── common/                # Shared schemas, utils
│   ├── schemas.py        # Shared Pydantic models
│   ├── utils.py          # Utility functions
│   └── config.py         # Configuration management
├── tests/                 # Test files
├── docker-compose.yml     # Service orchestration
├── requirements.txt       # Python dependencies
├── env.template          # Environment variables template
└── README.md             # This file
```

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

### Adding New Subtitle Sources

1. Create a new source class in `downloader/sources/`
2. Implement the required interface
3. Register the source in the downloader worker

### Adding New Translation Services

1. Create a new service class in `translator/services/`
2. Implement the required interface
3. Register the service in the translator worker

## Configuration

Key environment variables:

- `REDIS_URL`: Redis connection string
- `RABBITMQ_URL`: RabbitMQ connection string
- `OPENSUBTITLES_API_KEY`: OpenSubtitles API key
- `GOOGLE_TRANSLATE_API_KEY`: Google Translate API key

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License
