# Translator Service

The Translator Service processes subtitle files using OpenAI's GPT-5-nano model to translate subtitles from one language to another while maintaining timing, tone, and subtitle-appropriate formatting.

> **📖 See Also**: [Main README](../README.md) for project overview, setup instructions, and development guide.

## 🚀 Features

- **GPT-5-nano Translation**: Leverages OpenAI's efficient nano model for fast, accurate translations
- **Batch Processing**: Translates subtitles in chunks for optimal performance
- **SRT Format Support**: Parses and formats SubRip (.srt) subtitle files
- **Timing Preservation**: Maintains original subtitle timing and structure
- **Redis Integration**: Updates job status in real-time
- **Error Handling**: Graceful handling of API failures and malformed subtitles

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
OPENAI_MODEL=gpt-5-nano
OPENAI_MAX_TOKENS=4096
OPENAI_TEMPERATURE=0.3

# RabbitMQ Configuration
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Redis Configuration
REDIS_URL=redis://localhost:6379
```

### Model Parameters

- **OPENAI_MODEL**: Model to use (`gpt-5-nano` recommended for speed and cost)
- **OPENAI_MAX_TOKENS**: Maximum tokens per API call (4096 default)
- **OPENAI_TEMPERATURE**: Controls randomness (0.3 for consistent translations)

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
2. **SRT Parsing**: Subtitle file is parsed into timed segments
3. **Chunking**: Segments are split into batches (50 segments per chunk)
4. **Translation**: Each chunk is sent to GPT-5-nano with context
5. **Merging**: Translated text is merged back into timed segments
6. **Formatting**: Output is formatted back to SRT format
7. **Status Update**: Job status is updated to COMPLETED in Redis

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

The system uses a structured prompt format:

```
System: You are a professional subtitle translator...

User: Translate the following N subtitle segments...
Format your response exactly like this:
[1]
Translated text

[2]
Translated text

Subtitles to translate:
[1]
Original text

[2]
Original text
```

## 🎯 Supported Languages

GPT-5-nano supports translation between most language pairs. Common examples:

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
🤖 Using model: gpt-5-nano
🔌 Connecting to Redis...
🔌 Connecting to RabbitMQ...
📋 Declaring queue: subtitle.translation
🎧 Starting to consume translation messages...
```

### Processing Logs

```
📥 RECEIVED TRANSLATION TASK
Parsing SRT content...
Parsed 42 subtitle segments
Translating chunk 1/1 (42 segments)
✅ Updated job status to COMPLETED in Redis
✅ Translation completed successfully!
```

## 🚨 Error Handling

### API Errors

- **Rate Limits**: Automatic retry with exponential backoff (2 retries)
- **Timeouts**: 60-second timeout per request
- **Invalid API Key**: Worker runs in mock mode with warnings

### Subtitle Parsing Errors

- **Malformed SRT**: Skips invalid segments, processes valid ones
- **Missing Timestamps**: Logs warning and continues
- **Empty Files**: Returns error status to Redis

### Redis Connection Failures

- **Graceful Degradation**: Worker continues processing
- **Status Updates**: Logs warning if Redis update fails
- **Connection Retry**: Automatic reconnection on failure

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

- **Small File** (< 100 segments): ~5-10 seconds
- **Medium File** (100-500 segments): ~20-40 seconds
- **Large File** (> 500 segments): ~60-120 seconds

### Optimization Tips

1. **Batch Size**: Adjust chunk size based on segment complexity
2. **Concurrent Workers**: Run multiple worker instances for parallel processing
3. **Model Selection**: Use gpt-5-nano for speed, gpt-4 for quality
4. **Caching**: Consider caching common translations

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

