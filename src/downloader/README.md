# Downloader Service

The Downloader Service is a worker service that fetches subtitles from external sources (primarily OpenSubtitles) and publishes events to notify other services of download completion or failure.

> **📖 See Also**: [Main README](../README.md) for project overview, setup instructions, and development guide.

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- RabbitMQ running on `localhost:5672`
- Redis running on `localhost:6379`
- OpenSubtitles account (username and password)

### Installation

```bash
# Navigate to downloader directory
cd downloader

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp ../env.template ../.env

# Edit .env with your OpenSubtitles credentials
nano ../.env
```

### Running the Service

```bash
# Development mode (local)
python worker.py

# With Docker Compose
docker-compose up downloader
```

## 📋 Overview

The Downloader Service:

- **Consumes** download tasks from the `subtitle.download` RabbitMQ queue
- **Searches** for subtitles using OpenSubtitles XML-RPC API
- **Downloads** subtitle files to local storage
- **Publishes** events to RabbitMQ for other services to consume
- **Updates** job status in Redis

## 🔧 Configuration

### Environment Variables

Add these to your `.env` file:

```env
# OpenSubtitles Configuration
OPENSUBTITLES_USER_AGENT=get-my-subtitle v1.0
OPENSUBTITLES_USERNAME=your_username
OPENSUBTITLES_PASSWORD=your_password
OPENSUBTITLES_MAX_RETRIES=3
OPENSUBTITLES_RETRY_DELAY=1
OPENSUBTITLES_RETRY_MAX_DELAY=60
OPENSUBTITLES_RETRY_EXPONENTIAL_BASE=2

# RabbitMQ Configuration
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Redis Configuration
REDIS_URL=redis://localhost:6379

# File Storage
SUBTITLE_STORAGE_PATH=./storage/subtitles

# Logging
LOG_LEVEL=INFO
```

### OpenSubtitles Account Setup

1. Create an account at [OpenSubtitles.org](https://www.opensubtitles.org/)
2. Get your username and password
3. Add credentials to `.env` file

## 🏃 Running the Worker

### Local Development

```bash
# Ensure RabbitMQ and Redis are running
docker-compose up redis rabbitmq

# Run the downloader worker
cd downloader
python worker.py
```

### Docker

```bash
# Build and run with docker-compose
docker-compose up downloader

# View logs
docker-compose logs -f downloader
```

### Standalone Docker

```bash
# Build the image
docker build -t subtitle-downloader -f downloader/Dockerfile .

# Run the container
docker run \
  -e REDIS_URL=redis://host.docker.internal:6379 \
  -e RABBITMQ_URL=amqp://guest:guest@host.docker.internal:5672/ \
  -e OPENSUBTITLES_USERNAME=your_username \
  -e OPENSUBTITLES_PASSWORD=your_password \
  subtitle-downloader
```

## 📊 How It Works

### Message Processing Flow

1. **Message Reception**: Worker receives download task from `subtitle.download` queue
2. **Status Update**: Updates job status to `DOWNLOAD_IN_PROGRESS` in Redis
3. **Subtitle Search**: 
   - First attempts hash-based search (if video file is local)
   - Falls back to metadata search (title, IMDB ID)
4. **Subtitle Download**: Downloads subtitle file if found
5. **Event Publishing**: Publishes `SUBTITLE_READY` or `SUBTITLE_TRANSLATE_REQUESTED` event
6. **Status Update**: Consumer service updates final status based on events

### Search Strategy

The downloader uses a two-tier search strategy:

1. **Hash-Based Search** (Preferred):
   - Calculates OpenSubtitles hash for local video files
   - Most accurate matching method
   - Used when `video_url` points to a local file

2. **Metadata Search** (Fallback):
   - Searches by video title and/or IMDB ID
   - Used when hash is unavailable or hash search returns no results
   - Supports language filtering

### Message Format

The worker expects messages in this format:

```json
{
  "request_id": "uuid-here",
  "video_url": "/path/to/video.mp4",
  "video_title": "Sample Video",
  "imdb_id": "1234567",
  "language": "en"
}
```

## 🎯 Supported Subtitle Sources

### OpenSubtitles (Primary)

- **API**: XML-RPC
- **Authentication**: Username/Password
- **Search Methods**: Hash-based and metadata-based
- **Languages**: All languages supported by OpenSubtitles
- **Rate Limiting**: Automatic retry with exponential backoff

### Future Sources

The architecture supports adding additional subtitle sources:
- Subscene
- Podnapisi
- Addic7ed
- Custom sources

## 📝 Event Publishing

The downloader publishes the following events:

### SUBTITLE_READY

Published when subtitle is successfully downloaded:

```json
{
  "event_type": "subtitle.ready",
  "job_id": "uuid",
  "timestamp": "2024-01-01T00:00:00Z",
  "source": "downloader",
  "payload": {
    "subtitle_path": "/path/to/subtitle.srt",
    "language": "en",
    "download_url": "file:///path/to/subtitle.srt",
    "source": "opensubtitles"
  }
}
```

### SUBTITLE_TRANSLATE_REQUESTED

Published when subtitle is not found and translation is enabled:

```json
{
  "event_type": "subtitle.translate.requested",
  "job_id": "uuid",
  "timestamp": "2024-01-01T00:00:00Z",
  "source": "downloader",
  "payload": {
    "subtitle_file_path": "/subtitles/fallback_uuid.en.srt",
    "source_language": "en",
    "target_language": "he",
    "reason": "subtitle_not_found"
  }
}
```

### JOB_FAILED

Published when processing fails:

```json
{
  "event_type": "job.failed",
  "job_id": "uuid",
  "timestamp": "2024-01-01T00:00:00Z",
  "source": "downloader",
  "payload": {
    "error_message": "Error description",
    "error_type": "rate_limit|api_error|invalid_video_path"
  }
}
```

## 🚨 Error Handling

### Rate Limiting

- **Detection**: `OpenSubtitlesRateLimitError` exception
- **Response**: Publishes `JOB_FAILED` event with rate limit error
- **Retry**: Automatic retry with exponential backoff (configured via env vars)

### API Errors

- **Detection**: `OpenSubtitlesAPIError` or `OpenSubtitlesAuthenticationError`
- **Response**: Falls back to translation if enabled
- **Retry**: Automatic retry with exponential backoff

### Invalid Video Path

- **Detection**: Video URL is not a local file path
- **Response**: Publishes `JOB_FAILED` event
- **Reason**: Cannot save subtitle next to video file

### Translation Fallback

When subtitle is not found in the desired language:
1. Downloads subtitle in fallback language (usually English)
2. If `JELLYFIN_AUTO_TRANSLATE=true`: Publishes `SUBTITLE_TRANSLATE_REQUESTED` event
3. If `JELLYFIN_AUTO_TRANSLATE=false`: Publishes `SUBTITLE_READY` with fallback language
4. Translation task is enqueued directly by the downloader worker

**Language Configuration:**
- Uses centralized `SUBTITLE_DESIRED_LANGUAGE` and `SUBTITLE_FALLBACK_LANGUAGE` settings
- Automatically attempts fallback language if desired language not found
- No need to manually configure language per-request

## 🔍 Monitoring

### Logs

The worker provides detailed logging:

```
🚀 Starting Subtitle Downloader Worker
🔌 Connecting to Redis...
🔌 Connecting event publisher...
🔌 Connecting to OpenSubtitles API...
🔌 Connecting to RabbitMQ...
📋 Declaring queue: subtitle.download
🎧 Starting to consume messages...
```

### Processing Logs

```
📥 RECEIVED MESSAGE
🔍 Searching for subtitles: url=/path/to/video.mp4, title=Sample Video, language=en
📁 Local file detected, calculating hash...
📊 Calculated file hash: abc123... (size: 1234567890 bytes)
🔍 Searching by file hash: abc123...
✅ Found 5 subtitle(s) by hash search
📁 Will save subtitle to: /path/to/video.en.srt
✅ Downloaded subtitle! Published SUBTITLE_READY event for job uuid
✅ Message processed successfully!
```

## 🎨 Architecture

```
┌─────────────────┐
│  RabbitMQ Queue │
│  subtitle.      │
│  download       │
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│ Downloader Worker   │
│                     │
│ 1. Parse Message    │
│ 2. Search Subtitles │
│ 3. Download File    │
│ 4. Publish Event    │
└──────┬──────────────┘
       │
       ├──────────────┐
       │              │
       ▼              ▼
  ┌────────┐    ┌──────────┐
  │ Redis  │    │ RabbitMQ │
  │ Status │    │  Events  │
  └────────┘    └──────────┘
```

## 🔧 Troubleshooting

### Worker Not Starting

1. **Check RabbitMQ**:
   ```bash
   docker-compose ps rabbitmq
   # or
   rabbitmqctl status
   ```

2. **Check Redis**:
   ```bash
   redis-cli ping
   ```

3. **Verify Environment Variables**:
   ```bash
   echo $OPENSUBTITLES_USERNAME
   echo $OPENSUBTITLES_PASSWORD
   ```

### Authentication Failures

**Symptom**: `OpenSubtitlesAuthenticationError`

**Solutions**:
- Verify username and password in `.env`
- Check OpenSubtitles account is active
- Ensure credentials haven't been revoked

### Rate Limit Errors

**Symptom**: `OpenSubtitlesRateLimitError`

**Solutions**:
- Wait for rate limit to reset (usually 24 hours)
- Reduce concurrent download requests
- Use OpenSubtitles VIP account for higher limits

### No Subtitles Found

**Symptom**: Worker logs "No subtitle found"

**Solutions**:
- Verify video title/IMDB ID is correct
- Check if subtitles exist for the language requested
- Try different language codes
- Enable translation fallback

### File Path Issues

**Symptom**: "Cannot save subtitle: video is not a local file"

**Solutions**:
- Ensure `video_url` is a local file path (not HTTP URL)
- Check file permissions on video directory
- Verify video file exists and is accessible

## 📈 Performance

### Optimization Tips

1. **Hash-Based Search**: Always use local file paths for faster, more accurate matching
2. **Concurrent Workers**: Run multiple downloader instances for parallel processing
3. **Caching**: Consider caching search results for frequently requested videos
4. **Rate Limiting**: Respect OpenSubtitles rate limits to avoid temporary bans

### Benchmarks

- **Hash Search**: ~1-2 seconds
- **Metadata Search**: ~2-5 seconds
- **Download**: ~1-3 seconds
- **Total Processing**: ~3-8 seconds per subtitle

## 🔐 Security

- Store OpenSubtitles credentials in environment variables, never in code
- Use `.env` files locally, secrets management in production
- Rotate credentials regularly
- Monitor API usage for anomalies

## 🔗 Integration

### With Manager Service

The manager service enqueues download tasks:
- Manager publishes to `subtitle.download` queue
- Downloader consumes and processes
- Downloader publishes events back to RabbitMQ

### With Consumer Service

The consumer service processes events:
- Downloader publishes `SUBTITLE_READY` or `SUBTITLE_TRANSLATE_REQUESTED`
- Consumer updates job status in Redis
- Consumer records event history

### With Translator Service

When subtitle is not found:
- Downloader publishes `SUBTITLE_TRANSLATE_REQUESTED`
- Translator service picks up translation task
- Translator processes and publishes `SUBTITLE_TRANSLATED`

## 📚 API Reference

### OpenSubtitlesClient

```python
from downloader.opensubtitles_client import OpenSubtitlesClient

client = OpenSubtitlesClient()
await client.connect()

# Search by metadata
results = await client.search_subtitles(
    imdb_id="1234567",
    query="Sample Video",
    languages=["en"]
)

# Search by hash
results = await client.search_subtitles_by_hash(
    movie_hash="abc123...",
    file_size=1234567890,
    languages=["en"]
)

# Download subtitle
subtitle_path = await client.download_subtitle(
    subtitle_id="12345",
    output_path=Path("/path/to/subtitle.srt")
)
```

## 🤝 Contributing

1. Follow the existing code style
2. Add tests for new features
3. Update documentation
4. Submit pull requests to main branch

## 📄 License

MIT License - see main project README for details.

## 🔗 Related Documentation

- [Main README](../README.md) - Project overview and setup
- [Manager Service](../manager/README.md) - API and orchestration
- [Translator Service](../translator/README.md) - Translation worker
- [Consumer Service](../consumer/README.md) - Event consumer
- [Scanner Service](../scanner/README.md) - Media detection

