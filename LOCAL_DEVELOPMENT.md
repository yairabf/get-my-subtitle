# Local Development Guide

This guide explains how to run workers locally for debugging while using Docker for Redis and RabbitMQ.

## Prerequisites

1. **Docker** - For running Redis and RabbitMQ
2. **Python 3.11+** - For running workers locally
3. **Virtual environment** - Activate your venv
4. **Environment variables** - Ensure `.env` file is configured

## Infrastructure Setup

### Start Redis and RabbitMQ

```bash
# Start only Redis and RabbitMQ services
docker-compose up -d rabbitmq redis

# Verify they're running
docker-compose ps

# Check connectivity
nc -z localhost 6379 && echo "Redis OK" || echo "Redis not accessible"
nc -z localhost 5672 && echo "RabbitMQ OK" || echo "RabbitMQ not accessible"
```

### Access RabbitMQ Management UI

- **URL**: http://localhost:15672
- **Username**: `guest`
- **Password**: `guest`

## Environment Configuration

Ensure your `.env` file has the correct localhost URLs:

```env
REDIS_URL=redis://localhost:6379
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
```

**Note**: The default RabbitMQ credentials are `guest/guest`. If you see connection errors, wait a few seconds for RabbitMQ to fully start, then try again.

## Running Workers Locally

### 1. Manager Service (API Server)

The manager service provides the REST API and processes events.

```bash
# From project root
cd src/manager
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Or using the main entry point
python main.py
```

**Access**: http://localhost:8000
**API Docs**: http://localhost:8000/docs

### 2. Downloader Worker

Consumes download tasks from RabbitMQ and downloads subtitles.

```bash
# From project root
cd src/downloader
python worker.py

# Or using module syntax
python -m downloader.worker
```

### 3. Translator Worker

Consumes translation tasks and translates subtitles using OpenAI.

```bash
# From project root
cd src/translator
python worker.py

# Or using module syntax
python -m translator.worker
```

### 4. Consumer Worker

Consumes subtitle events and updates job status in Redis.

```bash
# From project root
cd src/consumer
python worker.py

# Or using module syntax
python -m consumer.worker
```

### 5. Scanner Service

Monitors file system and Jellyfin for new media files.

```bash
# From project root
cd src/scanner
python worker.py

# Or using module syntax
python -m scanner.worker
```

## Running Multiple Workers

You can run multiple workers in separate terminal windows:

**Terminal 1 - Manager:**
```bash
cd src/manager && python main.py
```

**Terminal 2 - Downloader:**
```bash
cd src/downloader && python worker.py
```

**Terminal 3 - Translator:**
```bash
cd src/translator && python worker.py
```

**Terminal 4 - Consumer:**
```bash
cd src/consumer && python worker.py
```

**Terminal 5 - Scanner:**
```bash
cd src/scanner && python worker.py
```

## Debugging Tips

### 1. Check Logs

All workers log to both console and files:
- Logs directory: `logs/`
- Files: `{service_name}_{date}.log`

### 2. Monitor RabbitMQ

- **Management UI**: http://localhost:15672
- Check queues: `subtitle.download`, `subtitle.translate`, `subtitle.events.consumer`
- Monitor message flow and queue depths

### 3. Check Redis

```bash
# Connect to Redis CLI
docker exec -it get-my-subtitle-redis-1 redis-cli

# List all keys
KEYS *

# Get a specific job
GET job:{job_id}
```

### 4. Test API Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Create download request
curl -X POST http://localhost:8000/subtitles/download \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "file:///path/to/video.mp4",
    "video_title": "Test Video",
    "language": "he"
  }'
```

### 5. Environment Variables

Make sure your `.env` file has:
- `OPENSUBTITLES_USERNAME` and `OPENSUBTITLES_PASSWORD` (required for downloader)
- `OPENAI_API_KEY` (required for translator)
- `SUBTITLE_DESIRED_LANGUAGE` and `SUBTITLE_FALLBACK_LANGUAGE`
- All other required variables

## Stopping Services

```bash
# Stop all Docker services
docker-compose down

# Stop only infrastructure (keep workers running)
docker-compose stop rabbitmq redis
```

## Troubleshooting

### Connection Errors

If workers can't connect to Redis/RabbitMQ:
1. Verify Docker containers are running: `docker-compose ps`
2. Check ports are accessible: `nc -z localhost 6379` and `nc -z localhost 5672`
3. Verify `.env` has correct URLs: `REDIS_URL=redis://localhost:6379`

### Import Errors

If you get import errors:
1. Make sure you're in the project root or `src/` directory
2. Activate your virtual environment
3. Install dependencies: `pip install -r requirements.txt`

### Port Conflicts

If ports are already in use:
- Manager: Change `API_PORT` in `.env`
- Scanner webhook: Change `SCANNER_WEBHOOK_PORT` in `.env`

## Quick Start Script

You can create a simple script to start all workers:

```bash
#!/bin/bash
# start-workers.sh

# Start infrastructure
docker-compose up -d rabbitmq redis

# Wait for services to be ready
sleep 5

# Start workers in background (or use separate terminals)
cd src/manager && python main.py &
cd src/downloader && python worker.py &
cd src/translator && python worker.py &
cd src/consumer && python worker.py &
cd src/scanner && python worker.py &
```

