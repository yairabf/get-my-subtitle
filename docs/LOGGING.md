# Logging Configuration

This document describes the centralized logging configuration for all services in the subtitle management system.

## Overview

The system uses a centralized logging configuration in `common/logging_config.py` that provides:

- **Consistent formatting** across all services
- **File and console logging** with different formats
- **Automatic log rotation** by date
- **Third-party logger noise reduction**
- **Configurable log levels** via environment variables

## Log Levels

Available log levels (from most to least verbose):

1. **DEBUG**: Detailed diagnostic information
2. **INFO**: General informational messages (default)
3. **WARNING**: Warning messages for potentially problematic situations
4. **ERROR**: Error messages for serious problems
5. **CRITICAL**: Critical messages for severe failures

Set the log level via environment variable:

```env
LOG_LEVEL=INFO
```

## Log Output Locations

### Console Output

All services log to stdout with a simple format:

```
2024-01-01 12:00:00 - INFO - Service started
2024-01-01 12:00:01 - ERROR - Failed to connect to database
```

### File Output

Logs are written to `./logs/` directory with daily rotation:

```
logs/
├── manager_20240101.log
├── downloader_20240101.log
└── translator_20240101.log
```

File logs include detailed information:

```
2024-01-01 12:00:00 - manager - INFO - [main.py:35] - Service started
2024-01-01 12:00:01 - manager - ERROR - [main.py:42] - Failed to connect
```

## Usage in Services

### Basic Usage

```python
from common.logging_config import setup_service_logging

# Initialize logger for your service
logger = setup_service_logging('my_service')

# Use the logger
logger.info("Service started")
logger.error("Something went wrong")
logger.debug("Detailed debug information")
```

### Advanced Usage

```python
from common.logging_config import ServiceLogger

# Create service logger with custom settings
service_logger = ServiceLogger('my_service', enable_file_logging=True)

# Use convenience methods
service_logger.info("Service started")
service_logger.error("Error occurred")
service_logger.warning("Warning message")
service_logger.exception("Exception with traceback")
```

### Custom Configuration

```python
from common.logging_config import setup_logging

# Setup with custom log file
logger = setup_logging(
    service_name='custom_service',
    log_file='./custom_logs/service.log',
    log_level='DEBUG'
)
```

## Service Integration

### Manager Service

```python
from common.logging_config import setup_service_logging

service_logger = setup_service_logging('manager', enable_file_logging=True)
logger = service_logger.logger

logger.info("Manager API starting...")
```

### Worker Services

```python
from common.logging_config import setup_service_logging

service_logger = setup_service_logging('downloader', enable_file_logging=True)
logger = service_logger.logger

logger.info("Downloader worker starting...")
```

## Third-Party Library Logging

To reduce noise from third-party libraries, their log levels are automatically set to WARNING:

- `aio_pika` - RabbitMQ async client
- `aiormq` - RabbitMQ low-level client
- `openai` - OpenAI SDK
- `httpx` - HTTP client
- `redis` - Redis client
- `asyncio` - Python async framework

You can customize this in your service:

```python
from common.logging_config import configure_third_party_loggers

# Set all third-party loggers to ERROR level
configure_third_party_loggers(level='ERROR')
```

## Log Format

### Console Format (Simple)

```
%(asctime)s - %(levelname)s - %(message)s
```

Example:
```
2024-01-01 12:00:00 - INFO - Service started
```

### File Format (Detailed)

```
%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s
```

Example:
```
2024-01-01 12:00:00 - manager - INFO - [main.py:35] - Service started
```

## Log Rotation

Logs are automatically rotated daily by including the date in the filename:

- `manager_20240101.log`
- `manager_20240102.log`
- `manager_20240103.log`

Old logs are preserved and can be cleaned up manually or with a cron job:

```bash
# Remove logs older than 30 days
find ./logs -name "*.log" -mtime +30 -delete
```

## Environment Variables

Configure logging behavior via environment variables:

```env
# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO
```

## Best Practices

### 1. Use Appropriate Log Levels

```python
# DEBUG: Detailed diagnostic info
logger.debug(f"Processing segment {i} of {total}")

# INFO: General informational messages
logger.info("Translation completed successfully")

# WARNING: Potentially problematic situations
logger.warning("API rate limit approaching")

# ERROR: Serious problems
logger.error("Failed to connect to Redis")

# CRITICAL: Severe failures
logger.critical("System out of memory")
```

### 2. Include Context

```python
# Bad
logger.error("Failed")

# Good
logger.error(f"Failed to translate job {job_id}: {error}")
```

### 3. Use Exception Logging

```python
try:
    result = process_data()
except Exception as e:
    # Automatically includes full traceback
    logger.exception(f"Error processing data: {e}")
```

### 4. Structured Logging

```python
logger.info(
    "Job completed",
    extra={
        "job_id": job_id,
        "duration": duration,
        "segments": segment_count
    }
)
```

## Monitoring and Analysis

### View Real-Time Logs

```bash
# Follow manager logs
tail -f logs/manager_$(date +%Y%m%d).log

# Follow all logs
tail -f logs/*.log

# Filter by log level
grep ERROR logs/manager_*.log
```

### Search Logs

```bash
# Find all errors in the last 7 days
find logs/ -name "*.log" -mtime -7 -exec grep ERROR {} \;

# Find specific job ID
grep "job_123" logs/*.log

# Count errors per service
grep -c ERROR logs/*.log
```

### Log Analysis Tools

Consider using tools like:

- **Logrotate**: Automatic log rotation and compression
- **ELK Stack**: Elasticsearch, Logstash, Kibana for log aggregation
- **Grafana Loki**: Log aggregation and querying
- **Sentry**: Error tracking and monitoring

## Troubleshooting

### Logs Not Appearing

1. Check log level setting:
   ```bash
   echo $LOG_LEVEL
   ```

2. Verify logs directory exists and is writable:
   ```bash
   mkdir -p logs
   chmod 755 logs
   ```

3. Check file permissions:
   ```bash
   ls -la logs/
   ```

### Too Verbose Logging

1. Increase log level:
   ```env
   LOG_LEVEL=WARNING
   ```

2. Reduce third-party logging:
   ```python
   configure_third_party_loggers(level='ERROR')
   ```

### Disk Space Issues

1. Set up log rotation:
   ```bash
   # /etc/logrotate.d/subtitle-system
   /path/to/logs/*.log {
       daily
       rotate 7
       compress
       missingok
       notifempty
   }
   ```

2. Clean old logs:
   ```bash
   find logs/ -name "*.log" -mtime +7 -delete
   ```

## Example Output

### Manager Service

```
2024-01-01 10:00:00 - INFO - Starting subtitle management API...
2024-01-01 10:00:00 - INFO - Connected to Redis successfully
2024-01-01 10:00:00 - INFO - Connected to RabbitMQ successfully
2024-01-01 10:00:00 - INFO - API startup complete
2024-01-01 10:00:15 - INFO - Subtitle request created: 550e8400-e29b-41d4-a716-446655440000
```

### Downloader Worker

```
2024-01-01 10:00:05 - INFO - 🚀 Starting Subtitle Downloader Worker
2024-01-01 10:00:05 - INFO - 🔌 Connecting to Redis...
2024-01-01 10:00:05 - INFO - 🔌 Connecting to RabbitMQ...
2024-01-01 10:00:05 - INFO - 🎧 Starting to consume messages...
2024-01-01 10:00:20 - INFO - 📥 RECEIVED MESSAGE
2024-01-01 10:00:21 - INFO - ✅ Message processed successfully!
```

### Translator Worker

```
2024-01-01 10:00:10 - INFO - 🚀 Starting Subtitle Translator Worker
2024-01-01 10:00:10 - INFO - 🤖 Using model: gpt-5-nano
2024-01-01 10:00:10 - INFO - Initialized OpenAI async client
2024-01-01 10:00:30 - INFO - Translating 42 segments from en to es
2024-01-01 10:00:45 - INFO - ✅ Translation completed successfully!
```

## Future Enhancements

Potential improvements to logging:

1. **Structured JSON logging** for better parsing
2. **Correlation IDs** for tracking requests across services
3. **Performance metrics** logging
4. **Log aggregation** to centralized logging service
5. **Alerting** based on log patterns
6. **Log sampling** for high-volume services

## Related Documentation

- [Configuration Guide](../README.md#configuration)
- [Monitoring Guide](./MONITORING.md)
- [Troubleshooting Guide](./TROUBLESHOOTING.md)

