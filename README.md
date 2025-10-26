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

```bash
# Format code
black .
isort .

# Run tests
pytest

# Run tests with coverage
pytest --cov=.
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
