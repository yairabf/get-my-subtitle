# Get My Subtitle

[![CI](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/ci.yml/badge.svg)](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/ci.yml)
[![Lint](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/lint.yml/badge.svg)](https://github.com/yairabramovitch/get-my-subtitle/actions/workflows/lint.yml)
[![codecov](https://codecov.io/gh/yairabramovitch/get-my-subtitle/branch/main/graph/badge.svg)](https://codecov.io/gh/yairabramovitch/get-my-subtitle)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

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
