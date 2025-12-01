# Translator Service

The Translator Service processes subtitle files using OpenAI's GPT models to translate subtitles from one language to another while maintaining timing, tone, and subtitle-appropriate formatting.

> **📖 See Also**: [Main README](../README.md) for project overview, setup instructions, and development guide.

## 🚀 Features

- **OpenAI Translation**: Supports GPT-4o-mini (recommended), GPT-4o, GPT-4, and other OpenAI models
- **Parallel Processing**: Processes 3-6 translation chunks simultaneously for 5-10x speedup
- **Batch Processing**: Translates subtitles in optimized batches (100 segments per chunk)
- **Checkpoint/Resume System**: Resume interrupted translations from saved checkpoints
- **SRT Format Support**: Parses and formats SubRip (.srt) subtitle files
- **Timing Preservation**: Maintains original subtitle timing and structure
- **Redis Integration**: Updates job status in real-time
- **Error Handling**: Graceful handling of API failures with exponential backoff retry

## 📋 Prerequisites

- Python 3.11+
- RabbitMQ running on `localhost:5672`
- Redis running on `localhost:6379`
- OpenAI API key with access to GPT-5-nano

## 🔧 Installation

```bash
# Navigate to translator directory
cd translator

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp ../env.template .env
nano .env  # Add your OPENAI_API_KEY
```

## ⚙️ Configuration

### Environment Variables

Add these to your `.env` file:

```env
# OpenAI Configuration
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=4096
OPENAI_TEMPERATURE=0.3

# Translation Parallel Processing
TRANSLATION_PARALLEL_REQUESTS=3            # For GPT-4o-mini (low rate limit)
TRANSLATION_PARALLEL_REQUESTS_HIGH_TIER=6  # For GPT-4o, GPT-4 (higher tier)

# Translation Token Limits
TRANSLATION_MAX_TOKENS_PER_CHUNK=8000       # Maximum tokens per chunk
TRANSLATION_TOKEN_SAFETY_MARGIN=0.8         # Safety margin (80% of limit)
TRANSLATION_MAX_SEGMENTS_PER_CHUNK=100      # Segments per chunk (100-200 recommended)

# Checkpoint Configuration
CHECKPOINT_ENABLED=true                    # Enable checkpointing
CHECKPOINT_CLEANUP_ON_SUCCESS=true         # Auto-cleanup after success

# RabbitMQ Configuration
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Redis Configuration
REDIS_URL=redis://localhost:6379
```

### Model Parameters

- **OPENAI_MODEL**: Model to use
  - `gpt-4o-mini` (recommended): Fast, cost-effective, optimized for translation
  - `gpt-4o`: Higher quality, faster than GPT-4
  - `gpt-4`: Highest quality, slower and more expensive
- **OPENAI_MAX_TOKENS**: Maximum tokens per API call (4096 default)
- **OPENAI_TEMPERATURE**: Controls randomness (0.3 for consistent translations)

### Parallel Processing Parameters

- **TRANSLATION_PARALLEL_REQUESTS**: Number of concurrent translation requests for GPT-4o-mini (default: 3)
- **TRANSLATION_PARALLEL_REQUESTS_HIGH_TIER**: Number of concurrent requests for higher tier models (default: 6)
- Model-based selection: Automatically uses appropriate value based on OPENAI_MODEL
- Speeds up translation by 5-10x by processing multiple chunks simultaneously

### Checkpoint Parameters

- **CHECKPOINT_ENABLED**: Enable checkpoint/resume functionality (default: true)
- **CHECKPOINT_CLEANUP_ON_SUCCESS**: Auto-delete checkpoints after completion (default: true)
- **CHECKPOINT_STORAGE_PATH**: Override checkpoint location (optional)

## 🏃 Running the Worker

### Development Mode

```bash
# With local RabbitMQ and Redis
python worker.py
```

### Production Mode

```bash
# With Docker Compose
docker-compose up translator
```

## 📊 How It Works

### Translation Pipeline

1. **Message Reception**: Worker receives translation task from `subtitle.translation` queue
2. **Checkpoint Check**: Checks for existing checkpoint to resume interrupted translations
3. **SRT Parsing**: Subtitle file is parsed into timed segments
4. **Chunking**: Segments are split into batches (100 segments per chunk, configurable)
5. **Parallel Translation**: Multiple chunks are processed simultaneously (3-6 concurrent requests)
6. **Checkpoint Saving**: Progress is saved after each batch for crash recovery
7. **Merging**: Translated text is merged back into timed segments
8. **Formatting**: Output is formatted back to SRT format
9. **Event Publishing**: SUBTITLE_TRANSLATED event is published to RabbitMQ
10. **Cleanup**: Checkpoint files are removed on successful completion

### Message Format

The worker expects messages in this format:

```json
{
  "request_id": "uuid-here",
  "subtitle_file_path": "/path/to/subtitle.srt",
  "source_language": "en",
  "target_language": "es"
}
```

### Translation Prompt Structure

The system uses a structured JSON-based prompt format for reliable parsing:

```json
System: You are a professional subtitle translator...

User: Translate the following N subtitle segments...
Return ONLY a JSON object with this structure:
{
  "translations": [
    {"segment": 1, "text": "Translated text"},
    {"segment": 2, "text": "Translated text"}
  ]
}

Subtitles to translate:
[1]
Original text

[2]
Original text
```

### Parallel Processing

- Processes 3-6 chunks simultaneously based on model tier
- Uses asyncio semaphore to control concurrency
- Respects API rate limits with configurable parallel request counts
- Automatically sorts results to maintain correct segment order
- Handles out-of-order completion gracefully

## 🎯 Supported Languages

OpenAI models support translation between most language pairs. Common examples:

- English (en) ↔ Spanish (es)
- English (en) ↔ French (fr)
- English (en) ↔ German (de)
- English (en) ↔ Japanese (ja)
- English (en) ↔ Chinese (zh)
- And many more...

## 📝 Subtitle Format

### Input Format (SRT)

```srt
1
00:00:01,000 --> 00:00:04,000
Hello world

2
00:00:04,500 --> 00:00:08,000
How are you today?
```

### Output Format

Same SRT structure with translated text:

```srt
1
00:00:01,000 --> 00:00:04,000
Hola mundo

2
00:00:04,500 --> 00:00:08,000
¿Cómo estás hoy?
```

## 🧪 Testing

```bash
# Run all translator tests
pytest tests/translator/ -v

# Run specific test file
pytest tests/translator/test_worker.py -v

# Run with coverage
pytest tests/translator/ --cov=translator --cov-report=html
```

## 🔍 Monitoring

### Logs

The worker provides detailed logging:

```
🚀 Starting Subtitle Translator Worker
🤖 Using model: gpt-4o-mini
🔌 Connecting to Redis...
🔌 Connecting event publisher...
🔌 Connecting to RabbitMQ...
📋 Declaring queue: subtitle.translation
🎧 Starting to consume translation messages...
```

### Processing Logs

```
📥 RECEIVED TRANSLATION TASK
📂 Checking for checkpoint...
Reading subtitle file: /path/to/subtitle.srt
Parsing SRT content...
Parsed 200 subtitle segments
Splitting into 2 chunks (max 100 segments per chunk)
🔄 Translating with 3 parallel requests...
Translating chunks: [0, 1]
✅ Translated chunk 0 (100 segments) - 15.2s
✅ Translated chunk 1 (100 segments) - 14.8s
💾 All chunks translated, merging results...
✅ Published SUBTITLE_TRANSLATED event for job uuid
✅ Translation completed successfully in 15.5s!
🧹 Cleaning up checkpoint file
```

## 🚨 Error Handling

### API Errors

- **Rate Limits**: Automatic retry with exponential backoff (up to 3 retries)
- **Timeouts**: 60-second timeout per request
- **Invalid API Key**: Worker runs in mock mode with warnings
- **Transient Failures**: Recognizes TranslationCountMismatchError as transient and retries

### Subtitle Parsing Errors

- **Malformed SRT**: Skips invalid segments, processes valid ones
- **Missing Timestamps**: Logs warning and continues
- **Empty Files**: Publishes JOB_FAILED event
- **Translation Count Mismatch**: Uses parsed segment numbers to identify missing translations
- **Partial Failures**: Handles out-of-order parallel completion with detailed error context

### Checkpoint System

- **Crash Recovery**: Resumes from last completed chunk
- **Validation**: Verifies checkpoint matches current request
- **Automatic Cleanup**: Removes checkpoints after successful completion
- **Manual Recovery**: Checkpoints can be manually inspected/recovered

### Redis Connection Failures

- **Graceful Degradation**: Worker continues processing
- **Status Updates**: Logs warning if Redis update fails
- **Connection Retry**: Automatic reconnection on failure
- **Event Publishing**: Falls back to event publishing if Redis is unavailable

## 🎨 Architecture

```
┌─────────────────┐
│  RabbitMQ Queue │
│  subtitle.      │
│  translation    │
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│ Translator Worker   │
│                     │
│ 1. Parse SRT        │
│ 2. Chunk Segments   │
│ 3. Call GPT-5-nano  │
│ 4. Format Output    │
│ 5. Update Redis     │
└──────┬──────────────┘
       │
       ├──────────────┐
       │              │
       ▼              ▼
  ┌────────┐    ┌──────────┐
  │ Redis  │    │ OpenAI   │
  │ Status │    │ GPT-5-nano│
  └────────┘    └──────────┘
```

## 🔧 Troubleshooting

### Worker Not Starting

1. Check RabbitMQ is running: `docker-compose ps rabbitmq`
2. Check Redis is running: `redis-cli ping`
3. Verify environment variables: `echo $OPENAI_API_KEY`

### Translation Failures

1. **Check API Key**: Ensure valid OpenAI API key
2. **Check Model Access**: Verify access to gpt-5-nano model
3. **Check Logs**: Review worker logs for error details

### Memory Issues

If processing very large subtitle files:

1. Reduce `max_segments` in chunking (default: 50)
2. Increase worker timeout settings
3. Monitor memory usage with `htop` or similar

## 📈 Performance

### Benchmarks

**With Parallel Processing (3 concurrent requests for GPT-4o-mini):**
- **Small File** (< 100 segments): ~5-10 seconds
- **Medium File** (100-500 segments): ~10-20 seconds (5-10x faster than serial)
- **Large File** (> 500 segments): ~20-40 seconds (5-10x faster than serial)

**Serial Processing (for comparison):**
- **Small File** (< 100 segments): ~10-15 seconds
- **Medium File** (100-500 segments): ~60-100 seconds
- **Large File** (> 500 segments): ~150-300 seconds

### Optimization Tips

1. **Parallel Requests**: Adjust TRANSLATION_PARALLEL_REQUESTS based on API tier
   - 3 for GPT-4o-mini (respects rate limits)
   - 6 for higher tier models (GPT-4o, GPT-4)
2. **Batch Size**: Optimize TRANSLATION_MAX_SEGMENTS_PER_CHUNK
   - 100-200 for GPT-4o-mini (recommended)
   - Up to 300-400 if server allows large payloads
3. **Concurrent Workers**: Run multiple worker instances for even more parallelism
4. **Model Selection**: Use gpt-4o-mini for speed, gpt-4o or gpt-4 for higher quality
5. **Checkpointing**: Enable for long translations to recover from crashes
6. **Caching**: Consider caching common translations (not implemented yet)

## 🔐 Security

- Store API keys in environment variables, never in code
- Use `.env` files locally, secrets management in production
- Rotate API keys regularly
- Monitor API usage for anomalies

## 📚 API Reference

### SubtitleTranslator

```python
class SubtitleTranslator:
    async def translate_batch(
        texts: List[str],
        source_language: str,
        target_language: str
    ) -> List[str]
```

### SRTParser

```python
class SRTParser:
    @staticmethod
    def parse(content: str) -> List[SubtitleSegment]
    
    @staticmethod
    def format(segments: List[SubtitleSegment]) -> str
```

## 🤝 Contributing

1. Follow the existing code style
2. Add tests for new features
3. Update documentation
4. Submit pull requests to main branch

## 📄 License

MIT License - see main project README for details.

