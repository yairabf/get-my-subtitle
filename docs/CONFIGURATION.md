# Configuration Guide

This guide explains how to configure the `.env` file and `docker-compose.yml` for different deployment scenarios.

> **📖 See Also**: [Main README](../README.md) for project overview and [Development Guide](DEVELOPMENT.md) for development setup.

## Table of Contents

- [Environment Variables (.env)](#environment-variables-env)
  - [Mandatory Variables](#mandatory-variables)
  - [Optional Variables](#optional-variables)
  - [Configuration by Use Case](#configuration-by-use-case)
- [Docker Compose Configuration](#docker-compose-configuration)
  - [Basic Configuration](#basic-configuration)
  - [Volume Configuration](#volume-configuration)
  - [Port Configuration](#port-configuration)
  - [Network Configuration](#network-configuration)
  - [Production Configuration](#production-configuration)

## Environment Variables (.env)

### Mandatory Variables

These variables **must** be set for the system to function:

#### OpenSubtitles Credentials
```env
OPENSUBTITLES_USERNAME=your_username
OPENSUBTITLES_PASSWORD=your_password
```
**Required for**: Subtitle downloading from OpenSubtitles  
**How to get**: Sign up at [OpenSubtitles.org](https://www.opensubtitles.org/)

#### OpenAI API Key
```env
OPENAI_API_KEY=sk-your-openai-api-key-here
```
**Required for**: Subtitle translation when subtitles aren't available  
**How to get**: Get your API key from [OpenAI Platform](https://platform.openai.com/)  
**Note**: Only required if you want translation functionality. If you only want to download existing subtitles, you can leave this empty (but translation features won't work).

### Optional Variables

These variables have sensible defaults but can be customized:

#### Infrastructure Configuration

```env
# Redis Configuration
REDIS_URL=redis://localhost:6379                    # Default: redis://localhost:6379
REDIS_JOB_TTL_COMPLETED=604800                      # Default: 604800 (7 days)
REDIS_JOB_TTL_FAILED=259200                         # Default: 259200 (3 days)
REDIS_JOB_TTL_ACTIVE=0                              # Default: 0 (no expiration)

# RabbitMQ Configuration
RABBITMQ_URL=amqp://guest:guest@localhost:5672/     # Default: amqp://guest:guest@localhost:5672/
```

**When to change:**
- If using external Redis/RabbitMQ servers (not Docker)
- If you want different job retention periods
- If using custom RabbitMQ credentials

#### API Configuration

```env
API_HOST=0.0.0.0                                     # Default: 0.0.0.0
API_PORT=8000                                        # Default: 8000
```

**When to change:**
- If you need to bind to a specific interface
- If port 8000 is already in use

#### Logging

```env
LOG_LEVEL=INFO                                       # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
```

**When to change:**
- Use `DEBUG` for troubleshooting
- Use `WARNING` or `ERROR` for production to reduce log volume

#### OpenSubtitles Configuration

```env
OPENSUBTITLES_USER_AGENT=get-my-subtitle v1.0       # Default: get-my-subtitle v1.0
OPENSUBTITLES_MAX_RETRIES=3                          # Default: 3
OPENSUBTITLES_RETRY_DELAY=1                          # Default: 1 (seconds)
OPENSUBTITLES_RETRY_MAX_DELAY=60                     # Default: 60 (seconds)
OPENSUBTITLES_RETRY_EXPONENTIAL_BASE=2               # Default: 2
```

**When to change:**
- If OpenSubtitles requires a specific user agent
- If you want more/less retry attempts for failed downloads

#### OpenAI Translation Configuration

```env
OPENAI_MODEL=gpt-5-nano                              # Default: gpt-5-nano
OPENAI_MAX_TOKENS=4096                               # Default: 4096
OPENAI_TEMPERATURE=0.3                               # Default: 0.3 (lower = more consistent)

# Translation Token Limits
TRANSLATION_MAX_TOKENS_PER_CHUNK=8000               # Default: 8000
TRANSLATION_TOKEN_SAFETY_MARGIN=0.8                  # Default: 0.8 (80% of limit)

# OpenAI Retry Configuration
OPENAI_MAX_RETRIES=3                                 # Default: 3
OPENAI_RETRY_INITIAL_DELAY=2.0                       # Default: 2.0 (seconds)
OPENAI_RETRY_MAX_DELAY=60.0                         # Default: 60.0 (seconds)
OPENAI_RETRY_EXPONENTIAL_BASE=2                      # Default: 2
```

**When to change:**
- If you want to use a different OpenAI model
- If you need to adjust translation chunk sizes for very long subtitles
- If you want different retry behavior for API failures

#### File Storage

```env
SUBTITLE_STORAGE_PATH=./storage/subtitles            # Default: ./storage/subtitles
```

**When to change:**
- If you want subtitles stored in a different location
- For production, use an absolute path or mounted volume path
- Example: `/mnt/storage/subtitles` or `/var/lib/get-my-subtitle/subtitles`

#### Subtitle Language Configuration

```env
# Subtitle Language Configuration
SUBTITLE_DESIRED_LANGUAGE=en              # The goal language (what you want to download)
SUBTITLE_FALLBACK_LANGUAGE=en             # Fallback when desired isn't found (then translated to desired)
```

**When to change:**
- Set `SUBTITLE_DESIRED_LANGUAGE` to the language you want subtitles in (e.g., "he" for Hebrew, "es" for Spanish)
- Set `SUBTITLE_FALLBACK_LANGUAGE` to a language that's commonly available (usually "en" for English)
- When desired language isn't found, the system will download in fallback language and automatically translate to desired

#### Jellyfin Integration

```env
# General Jellyfin Settings
JELLYFIN_URL=http://localhost:8096                   # Default: http://localhost:8096
JELLYFIN_API_KEY=                                     # Required if using Jellyfin integration
JELLYFIN_AUTO_TRANSLATE=true                         # Default: true

# WebSocket Configuration
JELLYFIN_WEBSOCKET_ENABLED=true                      # Default: true
JELLYFIN_WEBSOCKET_RECONNECT_DELAY=2.0               # Default: 2.0 (seconds)
JELLYFIN_WEBSOCKET_MAX_RECONNECT_DELAY=300.0         # Default: 300.0 (seconds)
JELLYFIN_FALLBACK_SYNC_ENABLED=true                  # Default: true
JELLYFIN_FALLBACK_SYNC_INTERVAL_HOURS=24             # Default: 24
```

**When to change:**
- **Required**: Set `JELLYFIN_URL` and `JELLYFIN_API_KEY` if using Jellyfin integration
- Set `JELLYFIN_AUTO_TRANSLATE=false` if you only want to download, not translate
- Adjust WebSocket settings if you have connection issues

**How to get Jellyfin API Key:**
1. Open Jellyfin web interface
2. Go to Dashboard → API Keys
3. Create a new API key
4. Copy the key to `JELLYFIN_API_KEY`

#### Scanner Configuration

```env
# File System Watcher
SCANNER_MEDIA_PATH=/media                            # Default: /media
SCANNER_WATCH_RECURSIVE=true                         # Default: true
SCANNER_MEDIA_EXTENSIONS=.mp4,.mkv,.avi,.mov,.m4v,.webm  # Default: .mp4,.mkv,.avi,.mov,.m4v,.webm
SCANNER_DEBOUNCE_SECONDS=2.0                         # Default: 2.0
SCANNER_AUTO_TRANSLATE=false                        # Default: false

# Webhook Server
SCANNER_WEBHOOK_HOST=0.0.0.0                         # Default: 0.0.0.0
SCANNER_WEBHOOK_PORT=8001                            # Default: 8001
```

**Note:** Scanner uses `SUBTITLE_DESIRED_LANGUAGE` for the language to download. See [Subtitle Language Configuration](#subtitle-language-configuration) above.

**When to change:**
- Set `SCANNER_MEDIA_PATH` to your media directory path
- Add/remove file extensions in `SCANNER_MEDIA_EXTENSIONS` based on your media types
- Adjust `SCANNER_DEBOUNCE_SECONDS` if files are being processed too quickly/slowly
- Set `SCANNER_DEFAULT_TARGET_LANGUAGE` if you want automatic translation for file system scans
- Change `SCANNER_WEBHOOK_PORT` if port 8001 is in use

### Configuration by Use Case

#### Minimal Setup (Download Only, No Translation)

```env
# Mandatory
OPENSUBTITLES_USERNAME=your_username
OPENSUBTITLES_PASSWORD=your_password

# Optional - can leave empty if not translating
OPENAI_API_KEY=
```

#### Full Setup (Download + Translation)

```env
# Mandatory
OPENSUBTITLES_USERNAME=your_username
OPENSUBTITLES_PASSWORD=your_password
OPENAI_API_KEY=sk-your-openai-api-key-here

# Recommended
JELLYFIN_URL=http://your-jellyfin-server:8096
JELLYFIN_API_KEY=your_jellyfin_api_key
JELLYFIN_DEFAULT_TARGET_LANGUAGE=he
```

#### Production Setup (Homelab/Server)

```env
# Mandatory
OPENSUBTITLES_USERNAME=your_username
OPENSUBTITLES_PASSWORD=your_password
OPENAI_API_KEY=sk-your-openai-api-key-here

# Infrastructure (if using external services)
REDIS_URL=redis://your-redis-server:6379
RABBITMQ_URL=amqp://user:pass@your-rabbitmq-server:5672/

# Storage (use absolute path)
SUBTITLE_STORAGE_PATH=/mnt/storage/subtitles

# Jellyfin
JELLYFIN_URL=http://your-jellyfin-server:8096
JELLYFIN_API_KEY=your_jellyfin_api_key
JELLYFIN_DEFAULT_TARGET_LANGUAGE=he

# Logging (less verbose in production)
LOG_LEVEL=WARNING
```

#### Development Setup

```env
# Mandatory
OPENSUBTITLES_USERNAME=your_username
OPENSUBTITLES_PASSWORD=your_password
OPENAI_API_KEY=sk-your-openai-api-key-here

# Development-friendly defaults
LOG_LEVEL=DEBUG
SUBTITLE_STORAGE_PATH=./storage/subtitles
```

## Docker Compose Configuration

The `docker-compose.yml` file orchestrates all services. Here's what you need to configure:

### Basic Configuration

The default `docker-compose.yml` is ready to use out of the box. No changes needed for basic local development.

### Volume Configuration

#### Development Volumes (Default)

The default configuration mounts source code as volumes for hot reload:

```yaml
volumes:
  - ./common:/app/common
  - ./manager:/app/manager
  - ./downloader:/app/downloader
  - ./translator:/app/translator
  - ./storage:/app/storage
```

**When to use**: Development, testing, or when you want code changes to reflect immediately

#### Production Volumes

For production, you typically want:
1. **Persistent subtitle storage** (not just `./storage`)
2. **Media directory access** (for scanner)
3. **No source code mounting** (use built images)

```yaml
services:
  translator:
    volumes:
      - subtitle-storage:/app/storage  # Named volume for persistence
      # Remove source code volumes for production
  
  scanner:
    volumes:
      - subtitle-storage:/app/storage
      - /path/to/your/media:/media:ro  # Mount your media directory (read-only)
      # Remove source code volumes for production

volumes:
  subtitle-storage:  # Named volume for persistent storage
```

**Example Production Volume Configuration:**

```yaml
services:
  translator:
    volumes:
      - /mnt/storage/subtitles:/app/storage  # Absolute path for production
  
  scanner:
    volumes:
      - /mnt/storage/subtitles:/app/storage
      - /mnt/media:/media:ro  # Your media library path
```

### Port Configuration

#### Default Ports

```yaml
services:
  manager:
    ports:
      - "8000:8000"      # API server
  
  scanner:
    ports:
      - "8001:8001"      # Webhook server
  
  rabbitmq:
    ports:
      - "5672:5672"      # AMQP protocol
      - "15672:15672"    # Management UI
  
  redis:
    ports:
      - "6379:6379"      # Redis protocol
```

#### Changing Ports

If ports conflict with other services:

```yaml
services:
  manager:
    ports:
      - "8080:8000"      # Access API on port 8080 instead of 8000
  
  scanner:
    ports:
      - "8081:8001"      # Access webhook on port 8081 instead of 8001
```

**Important**: If you change ports, update your `.env` file accordingly:
```env
API_PORT=8080
SCANNER_WEBHOOK_PORT=8081
```

#### Production Port Configuration

For production, you might want to:
1. **Remove port mappings** and use a reverse proxy (nginx/traefik)
2. **Only expose necessary ports**

```yaml
services:
  manager:
    # Remove ports - access via reverse proxy
    # ports:
    #   - "8000:8000"
  
  rabbitmq:
    ports:
      - "5672:5672"      # Keep for internal services
      # Remove 15672 or restrict access
      # - "15672:15672"
  
  redis:
    # Remove port - only accessible from Docker network
    # ports:
    #   - "6379:6379"
```

### Network Configuration

#### Default Network

By default, Docker Compose creates a network where services can communicate using service names:
- `redis` - Redis service
- `rabbitmq` - RabbitMQ service
- `manager` - Manager API service

The `.env` file uses `localhost` for local development, but Docker Compose overrides this:

```yaml
services:
  manager:
    environment:
      REDIS_URL: redis://redis:6379           # Uses service name
      RABBITMQ_URL: amqp://guest:guest@rabbitmq:5672/  # Uses service name
```

#### External Network

To connect to an external Docker network (e.g., shared with other services):

```yaml
services:
  manager:
    networks:
      - default
      - external-network

networks:
  external-network:
    external: true
    name: your-external-network-name
```

### Production Configuration

#### Resource Limits

Add resource limits for production:

```yaml
services:
  manager:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
  
  translator:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

#### Restart Policies

Ensure services restart automatically:

```yaml
services:
  manager:
    restart: unless-stopped
  
  downloader:
    restart: unless-stopped
  
  translator:
    restart: unless-stopped
  
  consumer:
    restart: unless-stopped
  
  scanner:
    restart: unless-stopped
```

#### Health Checks

The default configuration includes health checks. For production, you might want to adjust intervals:

```yaml
services:
  manager:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s      # Check every 30 seconds (default: 10s)
      timeout: 10s       # Timeout after 10 seconds (default: 5s)
      retries: 5         # Retry 5 times (default: 3)
      start_period: 60s  # Allow 60 seconds for startup (default: 30s)
```

### Complete Production Example

Here's a complete example of production-ready `docker-compose.yml`:

```yaml
version: "3.8"

services:
  rabbitmq:
    image: rabbitmq:3-management
    restart: unless-stopped
    ports:
      - "5672:5672"
    volumes:
      - rabbitmq-data:/var/lib/rabbitmq
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s

  redis:
    image: redis:latest
    restart: unless-stopped
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s

  manager:
    build:
      context: .
      dockerfile: ./manager/Dockerfile
    restart: unless-stopped
    env_file:
      - .env
    environment:
      REDIS_URL: redis://redis:6379
      RABBITMQ_URL: amqp://guest:guest@rabbitmq:5672/
    depends_on:
      redis:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s

  downloader:
    build:
      context: .
      dockerfile: ./downloader/Dockerfile
    restart: unless-stopped
    env_file:
      - .env
    environment:
      REDIS_URL: redis://redis:6379
      RABBITMQ_URL: amqp://guest:guest@rabbitmq:5672/
    depends_on:
      manager:
        condition: service_healthy

  translator:
    build:
      context: .
      dockerfile: ./translator/Dockerfile
    restart: unless-stopped
    volumes:
      - /mnt/storage/subtitles:/app/storage  # Production storage path
    env_file:
      - .env
    environment:
      REDIS_URL: redis://redis:6379
      RABBITMQ_URL: amqp://guest:guest@rabbitmq:5672/
    depends_on:
      manager:
        condition: service_healthy
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G

  consumer:
    build:
      context: .
      dockerfile: ./consumer/Dockerfile
    restart: unless-stopped
    env_file:
      - .env
    environment:
      REDIS_URL: redis://redis:6379
      RABBITMQ_URL: amqp://guest:guest@rabbitmq:5672/
    depends_on:
      manager:
        condition: service_healthy

  scanner:
    build:
      context: .
      dockerfile: ./scanner/Dockerfile
    restart: unless-stopped
    volumes:
      - /mnt/storage/subtitles:/app/storage
      - /mnt/media:/media:ro  # Your media library
    env_file:
      - .env
    environment:
      REDIS_URL: redis://redis:6379
      RABBITMQ_URL: amqp://guest:guest@rabbitmq:5672/
    depends_on:
      manager:
        condition: service_healthy

volumes:
  rabbitmq-data:
  redis-data:
```

## Quick Reference

### Minimum Required Configuration

1. **Create `.env` file:**
   ```bash
   cp env.template .env
   ```

2. **Set mandatory variables:**
   ```env
   OPENSUBTITLES_USERNAME=your_username
   OPENSUBTITLES_PASSWORD=your_password
   OPENAI_API_KEY=sk-your-key-here
   ```

3. **Start services:**
   ```bash
   docker-compose up -d
   ```

### Common Configuration Tasks

#### Change Storage Location

1. Update `.env`:
   ```env
   SUBTITLE_STORAGE_PATH=/mnt/storage/subtitles
   ```

2. Update `docker-compose.yml`:
   ```yaml
   translator:
     volumes:
       - /mnt/storage/subtitles:/app/storage
   ```

#### Connect to External Jellyfin

1. Update `.env`:
   ```env
   JELLYFIN_URL=http://192.168.1.100:8096
   JELLYFIN_API_KEY=your_api_key
   ```

2. No `docker-compose.yml` changes needed (uses HTTP)

#### Use External Redis/RabbitMQ

1. Update `.env`:
   ```env
   REDIS_URL=redis://192.168.1.100:6379
   RABBITMQ_URL=amqp://user:pass@192.168.1.100:5672/
   ```

2. Remove Redis/RabbitMQ services from `docker-compose.yml` or comment them out

3. Remove `depends_on` references to these services

## Troubleshooting

### Services Can't Connect

**Problem**: Services can't reach Redis/RabbitMQ

**Solution**: 
- In Docker Compose, use service names: `redis://redis:6379` (not `localhost`)
- The `docker-compose.yml` already overrides `.env` URLs for Docker networking
- For local development (hybrid mode), use `localhost` in `.env`

### Volumes Not Persisting

**Problem**: Subtitle files disappear after container restart

**Solution**:
- Use named volumes or absolute paths
- Don't use relative paths like `./storage` in production
- Check volume mounts in `docker-compose.yml`

### Port Conflicts

**Problem**: Port already in use

**Solution**:
- Change port mappings in `docker-compose.yml`
- Update corresponding `.env` variables if needed
- Check what's using the port: `lsof -i :8000`

For more troubleshooting help, see the [Development Guide](DEVELOPMENT.md#troubleshooting).



