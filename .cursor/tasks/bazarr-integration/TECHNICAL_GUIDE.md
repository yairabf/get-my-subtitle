# Bazarr Integration - Technical Guide

**Last Updated:** December 8, 2025  
**Status:** Planning Phase

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Event Flow](#event-flow)
3. [Data Flow](#data-flow)
4. [Source-Agnostic Design](#source-agnostic-design)
5. [Implementation Checklist](#implementation-checklist)
6. [Configuration Guide](#configuration-guide)
7. [Testing Guide](#testing-guide)
8. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### High-Level Architecture

```
┌──────────────────────────────────────────────────────┐
│  Media Library Ecosystem                             │
│  • Jellyfin/Plex/Emby (Media Server)                │
│  • Sonarr (TV Shows) / Radarr (Movies)              │
│  • Bazarr (Subtitle Management)                     │
└────────────────┬─────────────────────────────────────┘
                 │
                 │ Bazarr monitors library
                 │ Searches 20+ subtitle providers
                 │ Downloads best available subtitle
                 ↓
         ┌───────────────┐
         │    Bazarr     │
         │   Downloads   │
         │  EN/ES (not   │
         │   Hebrew)     │
         └───────┬───────┘
                 │
                 │ Webhook: subtitle_downloaded
                 ↓
┌────────────────────────────────────────────────────┐
│  Get My Subtitle - Manager Service (Adapter)       │
│                                                    │
│  Responsibilities:                                 │
│  1. Receive Bazarr webhook (Bazarr-specific)      │
│  2. Normalize to SubtitleResponse (Standard)      │
│  3. Publish SUBTITLE_TRANSLATE_REQUESTED (Std)    │
│  4. Enqueue TranslationTask (Standard)            │
│                                                    │
│  ↓ Everything below is standard format ↓          │
└────────────────┬───────────────────────────────────┘
                 │
                 ├─ Redis: Standard job storage
                 ├─ RabbitMQ: Standard events
                 └─ RabbitMQ: Standard tasks
                          ↓
                 ┌────────────────┐
                 │ Translation    │
                 │ Worker         │
                 │ (Source        │
                 │  Agnostic)     │
                 └────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Knows About Bazarr? |
|-----------|---------------|---------------------|
| **Bazarr** | Download subtitles from 20+ providers | N/A |
| **Manager Webhook** | Normalize Bazarr events to standard format | ✅ Yes (only here) |
| **Translation Worker** | Translate subtitles (any source) | ❌ No |
| **Consumer Worker** | Update job state (any source) | ❌ No |
| **Redis** | Store jobs (standard format) | ❌ No |
| **RabbitMQ** | Route events/tasks (standard format) | ❌ No |

---

## Event Flow

### Complete Event Flow Diagram

```
1. Bazarr Event
   ↓
   POST /webhooks/bazarr
   {
     "event_type": "subtitle_downloaded",
     "language": "en",
     "subtitle_path": "/media/video.en.srt",
     ...
   }

2. Manager Webhook Handler
   ↓
   • Validate payload (BazarrWebhookPayload)
   • Check: language == desired_language?
   • If NO → Continue
   • Create SubtitleResponse (standard)
   • Save to Redis
   • Read subtitle file from Bazarr path
   • Save to standard storage

3. Publish Event (Standard Format)
   ↓
   RabbitMQ Exchange: subtitle.events
   Routing Key: subtitle.translate.requested
   {
     "event_type": "subtitle.translate.requested",
     "job_id": "uuid",
     "source": "bazarr-webhook",    ← Only mention of Bazarr
     "payload": {
       "subtitle_file_path": "/storage/uuid.en.srt",
       "source_language": "en",
       "target_language": "he"
     }
   }

4. Consumer Worker
   ↓
   • Receives event
   • Updates Redis job status: TRANSLATE_QUEUED
   • Records event in job history

5. Enqueue Task (Standard Format)
   ↓
   RabbitMQ Queue: subtitle.translation
   {
     "request_id": "uuid",
     "subtitle_file_path": "/storage/uuid.en.srt",
     "source_language": "en",
     "target_language": "he"
   }

6. Translation Worker
   ↓
   • Picks up task from queue
   • Reads subtitle file
   • Translates using OpenAI
   • Saves translated file: /storage/uuid.he.srt
   • Publishes SUBTITLE_TRANSLATED event

7. Consumer Worker (Final)
   ↓
   • Receives SUBTITLE_TRANSLATED event
   • Updates Redis: status=COMPLETED
   • OPTIONAL: Copy to media folder (if Bazarr origin)

8. Result
   ↓
   • Original: /media/video.en.srt (Bazarr)
   • Translated: /storage/uuid.he.srt (Our service)
   • OPTIONAL: /media/video.he.srt (Copy from our service)
```

---

## Data Flow

### Data Transformation Pipeline

#### Input: Bazarr Webhook Payload

```json
{
  "event_type": "subtitle_downloaded",
  "media_type": "series",
  "media_title": "Breaking Bad - S05E14",
  "media_path": "/media/tv/Breaking Bad/Season 05/Breaking.Bad.S05E14.mkv",
  "series_id": 123,
  "episode_number": 14,
  "season_number": 5,
  "subtitle_path": "/media/tv/Breaking Bad/Season 05/Breaking.Bad.S05E14.en.srt",
  "language": "en",
  "provider": "opensubtitles",
  "score": 0.92,
  "imdb_id": "tt0959621"
}
```

#### Transformation 1: Redis Job (SubtitleResponse)

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "video_url": "/media/tv/Breaking Bad/Season 05/Breaking.Bad.S05E14.mkv",
  "video_title": "Breaking Bad - S05E14",
  "language": "en",
  "target_language": "he",
  "status": "translate_queued",
  "created_at": "2025-12-08T12:00:00Z",
  "updated_at": "2025-12-08T12:00:00Z",
  "metadata": {
    "source": "bazarr-webhook",
    "original_subtitle_path": "/media/.../Breaking.Bad.S05E14.en.srt",
    "bazarr_provider": "opensubtitles",
    "bazarr_score": 0.92
  }
}
```

#### Transformation 2: Event (SubtitleEvent)

```json
{
  "event_type": "subtitle.translate.requested",
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "timestamp": "2025-12-08T12:00:01Z",
  "source": "bazarr-webhook",
  "payload": {
    "subtitle_file_path": "/storage/subtitles/123e4567.en.srt",
    "source_language": "en",
    "target_language": "he",
    "bazarr_provider": "opensubtitles",
    "bazarr_score": 0.92,
    "original_bazarr_path": "/media/.../Breaking.Bad.S05E14.en.srt"
  }
}
```

#### Transformation 3: Task (TranslationTask)

```json
{
  "request_id": "123e4567-e89b-12d3-a456-426614174000",
  "subtitle_file_path": "/storage/subtitles/123e4567.en.srt",
  "source_language": "en",
  "target_language": "he"
}
```

**Note:** Translation Worker only sees Transformation 3 - completely agnostic to Bazarr.

---

## Source-Agnostic Design

### Why This Matters

**Problem:**
If Translation Worker knows about different sources (Bazarr, OpenSubtitles, API uploads), it becomes:
- ❌ Complex (multiple code paths)
- ❌ Hard to test (mock multiple inputs)
- ❌ Fragile (changes to one source affect all)
- ❌ Difficult to extend (new sources require worker changes)

**Solution:**
Manager normalizes all inputs to standard format:
- ✅ Translation Worker has single code path
- ✅ Easy to test (mock standard format)
- ✅ Resilient (source changes don't affect worker)
- ✅ Extensible (new sources only affect Manager)

### Comparison: All Sources Use Same Format

| Source | Input Format | Manager Normalizes To | Worker Receives |
|--------|-------------|----------------------|----------------|
| Bazarr Webhook | Bazarr-specific JSON | TranslationTask | Standard Task |
| OpenSubtitles | Downloader creates task | TranslationTask | Standard Task |
| Direct Upload | API creates task | TranslationTask | Standard Task |
| Scanner | Scanner creates task | TranslationTask | Standard Task |

**Result:** Translation Worker code is identical regardless of source!

---

## Implementation Checklist

### Phase 1: Task 001 - Webhook Handler

#### Prerequisites
- [ ] Bazarr deployed and accessible
- [ ] Bazarr configured with language profile (Hebrew > English > Spanish)
- [ ] Webhook URL configured in Bazarr
- [ ] Volume mounts configured for file access

#### Step 1: Create Test File (TDD)
- [ ] Create `tests/manager/test_bazarr_webhook.py`
- [ ] Write test cases (should fail initially)
- [ ] Run tests: `pytest tests/manager/test_bazarr_webhook.py -v`

#### Step 2: Implement Schema
- [ ] Add `BazarrWebhookPayload` to `src/manager/schemas.py`
- [ ] Add Bazarr config to `src/common/config.py`
- [ ] Update `.env` with Bazarr settings
- [ ] Run schema tests

#### Step 3: Implement Endpoint
- [ ] Add `POST /webhooks/bazarr` to `src/manager/main.py`
- [ ] Implement webhook handler logic
- [ ] Run endpoint tests
- [ ] Test error scenarios

#### Step 4: Integration Testing
- [ ] Deploy full stack with Bazarr
- [ ] Test with real media file
- [ ] Verify webhook delivery
- [ ] Verify translation triggered
- [ ] Verify Hebrew subtitle created

#### Step 5: Documentation
- [ ] Update README.md
- [ ] Create BAZARR_INTEGRATION.md
- [ ] Document configuration
- [ ] Document troubleshooting
- [ ] Create task summary document

---

## Configuration Guide

### Full Configuration Example

```env
# =============================================================================
# Subtitle Language Configuration
# =============================================================================
SUBTITLE_DESIRED_LANGUAGE=he              # Hebrew (primary)
SUBTITLE_FALLBACK_LANGUAGE=en             # English (secondary)

# =============================================================================
# Bazarr Integration - Task 001
# =============================================================================
# Enable Bazarr webhook integration
BAZARR_ENABLED=true

# Webhook authentication (optional but recommended)
BAZARR_WEBHOOK_SECRET=change-this-to-a-random-secret

# Keep original subtitle after translation
BAZARR_SAVE_ORIGINAL=true

# =============================================================================
# Bazarr API Integration - Task 002 (Future)
# =============================================================================
# BAZARR_URL=http://bazarr:6767
# BAZARR_API_KEY=your-bazarr-api-key
# SUBTITLE_PROVIDER_PRIORITY=opensubtitles,bazarr

# =============================================================================
# Media Folder Sync - Task 003 (Future)
# =============================================================================
# BAZARR_COPY_TO_MEDIA_FOLDER=true
# BAZARR_MEDIA_FOLDER_PERMISSIONS=644

# =============================================================================
# Existing Configuration (No Changes Required)
# =============================================================================
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_MODEL=gpt-4o-mini
TRANSLATION_PARALLEL_REQUESTS=3
TRANSLATION_MAX_SEGMENTS_PER_CHUNK=100
```

### Docker Compose Configuration

```yaml
version: '3.8'

services:
  # Existing services (manager, translator, etc.)
  manager:
    volumes:
      - /path/to/media:/media:ro    # Read access to media folder
      - ./storage:/storage           # Write access to storage

  # Bazarr service (optional for development)
  bazarr:
    image: lscr.io/linuxserver/bazarr:latest
    container_name: bazarr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=UTC
    volumes:
      - ./bazarr-config:/config
      - /path/to/media:/media        # Same path as manager
    ports:
      - "6767:6767"
    restart: unless-stopped
```

### Bazarr UI Configuration

**Access Bazarr:** http://localhost:6767

**Step 1: Languages**
```
Settings > Languages > Language Profile

Name: Hebrew-EN-ES

Languages (in order):
  1. Hebrew (he) ⭐ Primary
     ☑ Cutoff (stop searching once found)
  
  2. English (en) 🔄 Secondary
     ☐ Cutoff
  
  3. Spanish (es) 🔄 Tertiary
     ☐ Cutoff

Save
```

**Step 2: Webhook**
```
Settings > Notifications > Webhook

URL: http://get-my-subtitle-manager:8000/webhooks/bazarr

☑ On Movie Subtitle Download
☑ On Series Subtitle Download

Headers (optional):
  X-Bazarr-Secret: change-this-to-a-random-secret

Test Webhook  (Should return 200 OK or error details)

Save
```

**Step 3: Providers**
```
Settings > Providers

Configure your subtitle providers:
☑ OpenSubtitles.com
☑ OpenSubtitles.org
☑ Subscene
☑ Addic7ed
... (20+ available)

Save
```

---

## Testing Guide

### Manual Testing Workflow

#### Test 1: Hebrew Subtitle (Should Skip Translation)

```bash
# 1. Add media file with Hebrew subtitle available
# 2. Bazarr should find and download Hebrew subtitle
# 3. Check webhook response

# Expected logs:
# Manager: "Received Bazarr webhook: event_type=subtitle_downloaded"
# Manager: "Subtitle already in desired language (he), no translation needed"
# Manager: "Webhook response: status=skipped"

# Verify: No translation job created
curl http://localhost:8000/subtitles | jq '.[] | select(.language=="he")'
# Should return empty or very few results
```

#### Test 2: English Subtitle (Should Trigger Translation)

```bash
# 1. Add media file without Hebrew subtitle
# 2. Bazarr downloads English subtitle
# 3. Check webhook received

curl -X POST http://localhost:8000/webhooks/bazarr \
  -H "Content-Type: application/json" \
  -H "X-Bazarr-Secret: your-secret" \
  -d '{
    "event_type": "subtitle_downloaded",
    "media_type": "movie",
    "media_title": "Test Movie",
    "media_path": "/media/movies/Test.mkv",
    "subtitle_path": "/media/movies/Test.en.srt",
    "language": "en",
    "provider": "opensubtitles",
    "score": 0.95
  }'

# Expected response:
# {
#   "status": "success",
#   "message": "Translation job created: en → he",
#   "job_id": "..."
# }

# 4. Check job in Redis
docker exec -it redis redis-cli
KEYS subtitle:job:*
GET subtitle:job:<job_id>

# 5. Check RabbitMQ queue
# http://localhost:15672 (guest/guest)
# Should see message in subtitle.translation queue

# 6. Watch translator logs
docker-compose logs -f translator

# 7. Wait for completion (2-3 minutes)
# 8. Verify Hebrew subtitle created
ls -la storage/subtitles/*.he.srt
```

#### Test 3: Error Scenarios

```bash
# Test invalid payload
curl -X POST http://localhost:8000/webhooks/bazarr \
  -H "Content-Type: application/json" \
  -d '{"invalid": "payload"}'

# Expected: 422 Unprocessable Entity

# Test non-existent file
curl -X POST http://localhost:8000/webhooks/bazarr \
  -H "Content-Type: application/json" \
  -d '{
    ...
    "subtitle_path": "/nonexistent/file.srt",
    ...
  }'

# Expected: 500 Internal Server Error
# Job should be marked as FAILED in Redis
```

### Automated Testing

```bash
# Run all unit tests
pytest tests/manager/test_bazarr_webhook.py -v

# Run with coverage
pytest tests/manager/test_bazarr_webhook.py --cov=src/manager --cov-report=html

# Run integration tests
pytest tests/integration/test_bazarr_integration.py -v

# Run specific test class
pytest tests/manager/test_bazarr_webhook.py::TestBazarrWebhookEndpoint -v

# Run specific test
pytest tests/manager/test_bazarr_webhook.py::TestBazarrWebhookEndpoint::test_english_subtitle_triggers_translation -v
```

---

## Troubleshooting

### Issue 1: Webhook Not Received

**Symptoms:**
- Bazarr shows "Webhook sent successfully"
- No logs in Manager service

**Debugging Steps:**

```bash
# 1. Check Manager is running
docker-compose ps manager

# 2. Check Manager logs
docker-compose logs -f manager

# 3. Test webhook endpoint manually
curl http://localhost:8000/health
curl -X POST http://localhost:8000/webhooks/bazarr \
  -H "Content-Type: application/json" \
  -d '{"event_type":"test"}'

# 4. Check Bazarr webhook configuration
# Bazarr UI > Settings > Notifications > Webhook
# Click "Test" button - should see response

# 5. Check Docker networking
docker-compose exec bazarr ping get-my-subtitle-manager
docker-compose exec bazarr wget -O- http://get-my-subtitle-manager:8000/health

# 6. Check firewall rules (if external)
```

**Solutions:**
- Ensure URL is correct: `http://manager:8000/webhooks/bazarr` (Docker)
- Check Docker network configuration
- Verify ports are exposed correctly
- Check firewall rules

### Issue 2: Translation Not Triggered

**Symptoms:**
- Webhook received (200 OK)
- No translation happens

**Debugging Steps:**

```bash
# 1. Check webhook response body
# Should return status="success" and job_id

# 2. Check Redis for job
docker exec -it redis redis-cli
KEYS subtitle:job:*
GET subtitle:job:<job_id>
# Should show job with status=TRANSLATE_QUEUED

# 3. Check RabbitMQ for task
# http://localhost:15672
# Navigate to Queues > subtitle.translation
# Should show 1 message

# 4. Check translator worker is running
docker-compose ps translator
docker-compose logs -f translator

# 5. Check for errors in translator logs
docker-compose logs translator | grep ERROR

# 6. Check OpenAI API key
echo $OPENAI_API_KEY  # Should not be empty
```

**Solutions:**
- Ensure `BAZARR_ENABLED=true` in .env
- Verify translator worker is running
- Check OpenAI API key is valid
- Verify RabbitMQ connection is healthy

### Issue 3: File Permission Errors

**Symptoms:**
- Webhook returns 500 error
- Log shows "Permission denied" or "File not found"

**Debugging Steps:**

```bash
# 1. Check file exists
ls -la /path/from/webhook/subtitle.srt

# 2. Check file permissions
stat /path/from/webhook/subtitle.srt

# 3. Check Docker volume mounts
docker-compose config | grep volumes -A 5

# 4. Check container user
docker-compose exec manager whoami
docker-compose exec manager ls -la /media

# 5. Test file access from container
docker-compose exec manager cat /media/path/to/subtitle.srt
```

**Solutions:**
- Ensure volume mounts match Bazarr's paths
- Check file permissions (should be readable)
- Verify Docker user has read access
- Consider using `:ro` (read-only) mounts for security

### Issue 4: Webhook Secret Validation Fails

**Symptoms:**
- Webhook returns 401 Unauthorized
- Bazarr shows "Webhook failed"

**Debugging Steps:**

```bash
# 1. Check secret in .env
grep BAZARR_WEBHOOK_SECRET .env

# 2. Check secret in Bazarr UI
# Settings > Notifications > Webhook > Headers

# 3. Test manually with correct secret
curl -X POST http://localhost:8000/webhooks/bazarr \
  -H "X-Bazarr-Secret: correct-secret" \
  -H "Content-Type: application/json" \
  -d '{"event_type":"test"}'

# 4. Test with wrong secret
curl -X POST http://localhost:8000/webhooks/bazarr \
  -H "X-Bazarr-Secret: wrong-secret" \
  -H "Content-Type: application/json" \
  -d '{"event_type":"test"}'
# Should return 401
```

**Solutions:**
- Ensure secrets match exactly (case-sensitive)
- Check for whitespace in secret
- If optional: Leave `BAZARR_WEBHOOK_SECRET` empty
- Restart services after changing secrets

---

## Performance Considerations

### Webhook Response Time

**Target:** < 200ms for webhook acknowledgement

**Optimization:**
- Webhook returns immediately after enqueueing
- Translation happens asynchronously
- Don't wait for translation completion

### File I/O

**Optimization:**
- Read subtitle file async
- Stream large files instead of loading into memory
- Implement file size limits

### Concurrency

**Handling:**
- Multiple webhooks can arrive simultaneously
- Redis handles concurrent job creation (UUIDs prevent conflicts)
- RabbitMQ handles concurrent task enqueueing
- No locking needed

---

## Security Best Practices

### 1. Webhook Authentication
- ✅ Use webhook secret (optional but recommended)
- ✅ Validate X-Bazarr-Secret header
- ✅ Use constant-time comparison

### 2. Path Validation
- ✅ Validate subtitle_path from webhook
- ✅ Prevent path traversal attacks
- ✅ Ensure file within expected directories

### 3. Logging
- ✅ Never log secrets
- ✅ Log job IDs, not full file paths
- ✅ Use appropriate log levels

### 4. Error Messages
- ✅ Don't expose internal paths in responses
- ✅ Generic error messages for external clients
- ✅ Detailed errors in logs only

---

## Next Steps

1. **Review this guide**
2. **Deploy Bazarr** (Docker recommended)
3. **Configure Bazarr** (language profile + webhook)
4. **Start Task 001** (TDD: tests first!)
5. **Follow implementation checklist**
6. **Test thoroughly**
7. **Document findings**
8. **Create summary document**

---

**Questions or Issues?**
- Check troubleshooting section
- Review logs: `docker-compose logs -f`
- Test webhook manually: `curl http://localhost:8000/webhooks/bazarr`
- Verify configuration: `docker-compose config`

**Good luck with the implementation! 🚀**

