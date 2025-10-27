# Manager Service

The Manager Service is the central API and orchestrator for the subtitle management system. It handles subtitle processing requests, manages the workflow, and coordinates with worker services through RabbitMQ.

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- RabbitMQ running on `localhost:5672`
- Redis running on `localhost:6379`

### Installation

```bash
# Navigate to manager directory
cd manager

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp ../env.template .env

# Edit .env with your configuration
nano .env
```

### Running the Service

```bash
# Development mode with auto-reload
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Production mode
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## 📚 API Documentation

### Interactive Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Core Endpoints

#### Health Check
```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "version": "1.0.0"
}
```

#### Request Subtitle Download
```http
POST /subtitles/download
Content-Type: application/json

{
  "video_url": "https://example.com/video.mp4",
  "video_title": "Sample Video",
  "language": "en",
  "target_language": null,
  "preferred_sources": ["opensubtitles"]
}
```

**Workflow:**
1. Client calls this endpoint with video details
2. Manager creates job record and publishes SUBTITLE_DOWNLOAD_REQUESTED
3. Downloader service picks it up and downloads the file
4. Downloader publishes SUBTITLE_READY
5. Manager updates job status
6. Client can check status via `/subtitles/status/{job_id}`
7. Client can initiate translation via `/subtitles/translate` if needed

#### Get Detailed Subtitle Job Information
```http
GET /subtitles/{job_id}
```

Returns full details about a subtitle job including video information, timestamps, and status.

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "video_url": "https://example.com/video.mp4",
  "video_title": "Sample Video",
  "language": "en",
  "target_language": "es",
  "status": "processing",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:05:00Z",
  "error_message": null,
  "download_url": null
}
```

#### List All Requests
```http
GET /subtitles
```

#### Get Queue Status
```http
GET /queue/status
```

**Response:**
```json
{
  "download_queue_size": 5,
  "translation_queue_size": 2,
  "active_workers": {
    "downloader": 2,
    "translator": 1
  }
}
```

#### Download Processed Subtitles (Legacy)
```http
POST /subtitles/{request_id}/download
```

**Response:**
```json
{
  "download_url": "https://example.com/subtitles/123e4567-e89b-12d3-a456-426614174000.srt",
  "message": "Subtitles ready for download"
}
```

#### Translate Subtitle File by Path
```http
POST /subtitles/translate
```

Enqueue a subtitle file for translation by providing its file path. The translator worker will read the file and send its content to OpenAI API for translation.

**Request:**
```json
{
  "subtitle_path": "/path/to/subtitle.srt",
  "source_language": "en",
  "target_language": "es",
  "video_title": "Optional Title"
}
```

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "video_url": "",
  "video_title": "Optional Title",
  "language": "en",
  "target_language": "es",
  "status": "pending",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

#### Get Job Status with Progress
```http
GET /subtitles/status/{job_id}
```

Get simplified status information with progress percentage.

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "downloading",
  "progress": 25,
  "message": "Status: downloading"
}
```

Progress values:
- `pending`: 0%
- `downloading`: 25%
- `translating`: 75%
- `completed`: 100%
- `failed`: 0%

#### Jellyfin Webhook
```http
POST /webhooks/jellyfin
```

Webhook endpoint for Jellyfin media server integration. Automatically processes library item added/updated events for movies and episodes.

**Request:**
```json
{
  "event": "library.item.added",
  "item_type": "Movie",
  "item_name": "Sample Movie",
  "item_path": "/media/movies/sample.mp4",
  "item_id": "abc123",
  "library_name": "Movies",
  "video_url": "http://jellyfin.local/videos/abc123"
}
```

**Response:**
```json
{
  "status": "received",
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "message": "Subtitle processing queued for Sample Movie"
}
```

**Ignored Events:**
- Non-video items (Audio, Books, etc.)
- Events other than `library.item.added` or `library.item.updated`

**Configuration:**
Set these environment variables to control webhook behavior:
- `JELLYFIN_DEFAULT_SOURCE_LANGUAGE`: Default source language (default: "en")
- `JELLYFIN_DEFAULT_TARGET_LANGUAGE`: Default target language (default: None)
- `JELLYFIN_AUTO_TRANSLATE`: Enable automatic translation (default: true)

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the manager directory:

```env
# RabbitMQ Configuration
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Redis Configuration
REDIS_URL=redis://localhost:6379

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Logging
LOG_LEVEL=INFO

# Subtitle Sources (optional)
OPENSUBTITLES_USERNAME=your_username
OPENSUBTITLES_PASSWORD=your_password
OPENSUBTITLES_API_KEY=your_api_key

# Translation Service (optional)
OPENAI_API_KEY=your_api_key
OPENAI_MODEL=gpt-5-nano

# File Storage
SUBTITLE_STORAGE_PATH=./storage/subtitles

# Jellyfin Integration
JELLYFIN_DEFAULT_SOURCE_LANGUAGE=en
JELLYFIN_DEFAULT_TARGET_LANGUAGE=es
JELLYFIN_AUTO_TRANSLATE=true
```

## 🏗️ Architecture

### Components

1. **FastAPI Application** (`main.py`)
   - RESTful API endpoints
   - Request validation and processing
   - Response formatting

2. **Orchestrator** (`orchestrator.py`)
   - RabbitMQ message publishing
   - Queue management
   - Worker coordination

3. **Schemas** (`schemas.py`)
   - Pydantic models for request/response validation
   - Data type definitions

### Message Flow

```mermaid
graph TD
    A[Client Request] --> B[FastAPI Manager]
    B --> C[Request Validation]
    C --> D[Create Subtitle Response]
    D --> E[Publish to RabbitMQ]
    E --> F[Downloader Worker]
    F --> G[Translator Worker]
    G --> H[Update Status]
    H --> I[Client Polls Status]
```

### Queue Structure

- **Download Queue**: `subtitle.download`
  - Messages: `DownloadTask`
  - Purpose: Fetch subtitles from external sources

- **Translation Queue**: `subtitle.translation`
  - Messages: `TranslationTask`
  - Purpose: Translate subtitles to target language

## 🧪 Testing

### Manual Testing

```bash
# Health check
curl http://localhost:8000/health

# Test queue message
curl -X POST http://localhost:8000/test/queue-message

# Create subtitle request
curl -X POST http://localhost:8000/subtitles/request \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://example.com/video.mp4",
    "video_title": "Test Video",
    "language": "en",
    "target_language": "es"
  }'
```

### Automated Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test file
pytest tests/manager/test_api.py
```

## 🐳 Docker Support

### Build and Run

```bash
# Build the image
docker build -t subtitle-manager .

# Run the container
docker run -p 8000:8000 \
  -e RABBITMQ_URL=amqp://guest:guest@host.docker.internal:5672/ \
  -e REDIS_URL=redis://host.docker.internal:6379 \
  subtitle-manager
```

### Docker Compose

The manager service is included in the main `docker-compose.yml`:

```yaml
manager:
  build: ./manager
  ports:
    - "8000:8000"
  environment:
    - REDIS_URL=redis://redis:6379
    - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
  depends_on:
    - redis
    - rabbitmq
```

## 📊 Monitoring

### Health Checks

- **Basic Health**: `GET /health`
- **Queue Status**: `GET /queue/status`
- **RabbitMQ Management**: http://localhost:15672

### Logging

The service uses structured logging with configurable levels:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

Log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

## 🔒 Security

### Authentication

Currently, the API is open. For production, consider:

- API key authentication
- JWT tokens
- OAuth2 integration
- Rate limiting

### Input Validation

All inputs are validated using Pydantic schemas:

- URL validation for video URLs
- Language code validation
- File path sanitization
- Request size limits

## 🚨 Error Handling

### Common Error Responses

```json
{
  "detail": "Subtitle request not found"
}
```

**Status Codes:**
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `404` - Not Found
- `500` - Internal Server Error

### Graceful Degradation

- **RabbitMQ Unavailable**: Falls back to mock mode
- **Redis Unavailable**: Graceful degradation with logging (jobs won't be persisted)
- **Worker Unavailable**: Queues messages for later processing

## 💾 Redis Job Tracking

The manager uses Redis as a lightweight in-memory datastore to track subtitle processing jobs. This provides persistent job tracking across service restarts and enables real-time status lookups.

### Job Lifecycle

Jobs progress through the following states:

1. **PENDING**: Job created, waiting to be queued
2. **DOWNLOADING**: Job queued to downloader worker
3. **TRANSLATING**: Download complete, queued to translator worker
4. **COMPLETED**: All processing complete, subtitle ready
5. **FAILED**: Processing failed at any stage

### Redis Key Pattern

Jobs are stored using the pattern: `job:{job_id}`

Example: `job:123e4567-e89b-12d3-a456-426614174000`

### TTL (Time-to-Live) Policy

Jobs automatically expire based on their status to manage storage:

- **Completed jobs**: 7 days (604,800 seconds)
- **Failed jobs**: 3 days (259,200 seconds)
- **Active jobs** (pending, downloading, translating): No expiration

### Job Data Structure

Each job is stored as a JSON-serialized `SubtitleResponse` object containing:

```json
{
  "id": "uuid",
  "video_url": "string",
  "video_title": "string",
  "language": "string",
  "target_language": "string",
  "status": "pending|downloading|translating|completed|failed",
  "created_at": "timestamp",
  "updated_at": "timestamp",
  "error_message": "string|null",
  "download_url": "string|null"
}
```

### Configuration

Configure Redis TTL values in your `.env` file:

```env
REDIS_JOB_TTL_COMPLETED=604800  # 7 days
REDIS_JOB_TTL_FAILED=259200     # 3 days
REDIS_JOB_TTL_ACTIVE=0          # No expiration
```

### Job Operations

The Redis client (`common/redis_client.py`) provides:

- `save_job(job)`: Store or update a job
- `get_job(job_id)`: Retrieve a job by ID
- `update_job_status(job_id, status, ...)`: Update job status
- `list_jobs(status_filter)`: List all jobs (optionally filtered)
- `delete_job(job_id)`: Remove a job
- `health_check()`: Check Redis connectivity

### Benefits

- **Persistence**: Jobs survive service restarts
- **Fast lookups**: O(1) retrieval by job ID
- **Automatic cleanup**: TTL-based expiration
- **Distributed access**: Workers can update jobs directly
- **No database overhead**: Lightweight in-memory storage

### Troubleshooting Redis Connectivity

If Redis is unavailable:

1. **Check Redis is running**:
   ```bash
   docker-compose ps redis
   # or
   redis-cli ping
   ```

2. **Verify connection string**:
   ```env
   REDIS_URL=redis://localhost:6379
   ```

3. **Check logs**:
   ```bash
   # Manager logs will show Redis connection status
   tail -f logs/manager.log
   ```

4. **Test connection**:
   ```python
   import redis.asyncio as redis
   client = await redis.from_url("redis://localhost:6379")
   await client.ping()
   ```

The system will continue to operate even if Redis is unavailable, but jobs will not be persisted across restarts.

## 🔄 Development

### Code Structure

```
manager/
├── main.py              # FastAPI application
├── orchestrator.py      # RabbitMQ orchestration
├── schemas.py          # Pydantic models
├── requirements.txt    # Dependencies
├── Dockerfile         # Container definition
└── README.md          # This file
```

### Adding New Endpoints

1. Define the schema in `schemas.py`
2. Add the route in `main.py`
3. Update the orchestrator if needed
4. Add tests in `tests/manager/`

### Code Quality

```bash
# Format code
black .

# Sort imports
isort .

# Type checking
mypy .
```

## 📈 Performance

### Optimization Tips

- Use connection pooling for RabbitMQ
- Implement Redis caching for frequent requests
- Add request batching for bulk operations
- Use async/await throughout

### Scaling

- Horizontal scaling with multiple manager instances
- Load balancing with nginx or similar
- Database clustering for high availability
- Message queue clustering

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

MIT License - see the main project README for details.
