# Consumer Service

The Consumer Service is a dedicated event consumer that listens to subtitle processing events from RabbitMQ and updates job states in Redis. It provides decoupling between workers and state management, enabling better observability and auditability.

> **📖 See Also**: [Main README](../README.md) for project overview, setup instructions, and development guide.

## Purpose

- **Event Consumption**: Listens to events published to the `subtitle.events` topic exchange
- **State Management**: Updates job statuses in Redis based on events
- **Event History**: Records complete event history for each job
- **Audit Trail**: Maintains a timeline of all workflow events

## Architecture

### Event Flow

```
Worker → RabbitMQ (Event) → Consumer → Redis (Update Status + Record Event)
```

### Event Types Handled

The consumer listens to the following event types:

1. **subtitle.download.requested** - Download initiated by manager
2. **subtitle.ready** - Subtitle successfully downloaded
3. **subtitle.translate.requested** - Translation initiated
4. **subtitle.translated** - Translation completed successfully
5. **job.failed** - Any job failure

### Routing Patterns

The consumer binds to the topic exchange with these routing patterns:
- `subtitle.*` - All subtitle-related events
- `job.*` - All job-related events

## Configuration

### Environment Variables

```env
REDIS_URL=redis://localhost:6379
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
LOG_LEVEL=INFO
```

### Exchange Configuration

- **Exchange Name**: `subtitle.events`
- **Exchange Type**: `topic`
- **Durable**: `true`

### Queue Configuration

- **Queue Name**: `subtitle.events.consumer`
- **Durable**: `true`
- **Prefetch Count**: `1` (one message at a time)

## Event Handlers

### handle_subtitle_ready

Updates job status to `DONE` when subtitle is successfully downloaded.

**Payload**:
```json
{
  "subtitle_path": "/path/to/subtitle.srt",
  "language": "en",
  "download_url": "https://example.com/subtitle.srt"
}
```

### handle_subtitle_translated

Updates job status to `DONE` when translation is complete.

**Payload**:
```json
{
  "translated_path": "/path/to/translated.srt",
  "source_language": "en",
  "target_language": "he",
  "download_url": "https://example.com/translated.srt"
}
```

### handle_job_failed

Updates job status to `FAILED` and records error message.

**Payload**:
```json
{
  "error_message": "Description of what went wrong"
}
```

### handle_download_requested / handle_translate_requested

Records events in history without changing status (status already updated by manager).

## Running the Consumer

### Local Development

```bash
# Ensure Redis and RabbitMQ are running
docker-compose up redis rabbitmq

# Run the consumer
cd consumer
python worker.py
```

### Docker

```bash
# Build and run with docker-compose
docker-compose up consumer

# View logs
docker-compose logs -f consumer
```

### Standalone Docker

```bash
# Build the image
docker build -t subtitle-consumer -f consumer/Dockerfile .

# Run the container
docker run \
  -e REDIS_URL=redis://host.docker.internal:6379 \
  -e RABBITMQ_URL=amqp://guest:guest@host.docker.internal:5672/ \
  subtitle-consumer
```

## Monitoring

### Logging

The consumer logs all events with structured logging:

```
📬 RECEIVED EVENT: subtitle.ready
📥 Handling SUBTITLE_READY for job abc-123
✅ Successfully processed SUBTITLE_READY for job abc-123
```

### Health Checks

The consumer includes a basic health check that verifies Redis connectivity.

## Error Handling

### Graceful Degradation

- **Redis Unavailable**: Logs warnings, continues processing events
- **Invalid Event Data**: Logs error, acknowledges message to prevent requeuing
- **Processing Errors**: Logs error with full context, acknowledges message

### Retry Logic

- Uses RabbitMQ's built-in retry mechanisms
- Messages are acknowledged after processing (even on error)
- Failed events are logged for manual investigation

## Development

### Adding New Event Handlers

1. Add new event type to `common/schemas.py`:
   ```python
   class EventType(str, Enum):
       NEW_EVENT_TYPE = "new.event.type"
   ```

2. Create handler method in `consumer/worker.py`:
   ```python
   async def handle_new_event(self, event: SubtitleEvent) -> None:
       """Handle new event type."""
       # Process event
       await redis_client.update_phase(...)
       await redis_client.record_event(...)
   ```

3. Add routing in `process_event` method:
   ```python
   elif event.event_type == EventType.NEW_EVENT_TYPE:
       await self.handle_new_event(event)
   ```

### Testing

```bash
# Run consumer tests
pytest tests/consumer/

# Run with coverage
pytest tests/consumer/ --cov=consumer --cov-report=html
```

## Troubleshooting

### Consumer Not Receiving Events

1. **Check RabbitMQ Connection**:
   ```bash
   # Verify exchange exists
   curl -u guest:guest http://localhost:15672/api/exchanges/%2F/subtitle.events
   ```

2. **Check Queue Bindings**:
   ```bash
   # Verify queue bindings
   curl -u guest:guest http://localhost:15672/api/queues/%2F/subtitle.events.consumer/bindings
   ```

3. **Check Consumer Logs**:
   ```bash
   docker-compose logs -f consumer
   ```

### Events Not Being Recorded

1. **Verify Redis Connection**:
   ```bash
   redis-cli ping
   ```

2. **Check Event History**:
   ```bash
   redis-cli LRANGE "job:events:<job-id>" 0 -1
   ```

3. **Check Job Status**:
   ```bash
   redis-cli GET "job:<job-id>"
   ```

## Performance

### Throughput

- Processes events sequentially (prefetch_count=1)
- Suitable for most subtitle processing workloads
- Can be scaled horizontally by running multiple consumers

### Resource Usage

- **Memory**: ~50MB base + event processing overhead
- **CPU**: Low (event processing is lightweight)
- **Network**: Minimal (small event payloads)

### Scaling

To handle higher event volumes:

1. **Horizontal Scaling**: Run multiple consumer instances
2. **Dedicated Queues**: Create separate queues for different event types
3. **Batch Processing**: Increase prefetch_count (with caution)

## Integration

### With Manager Service

The consumer complements the manager by:
- Handling event-based status updates
- Maintaining event history
- Decoupling state management from API logic

### With Workers

Workers publish events, consumer processes them:
- Workers don't need direct Redis access for status updates
- Consumer provides centralized state management
- Clean separation of concerns

## Future Enhancements

- **Metrics Collection**: Track event processing times, counts
- **Dead Letter Queue**: Handle permanently failed events
- **Event Replay**: Support replaying events for debugging
- **Conditional Routing**: Route events based on content
- **Multiple Consumers**: Specialized consumers for different event types

