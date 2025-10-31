# Manual Testing Guide - OpenSubtitles API Integration

## Prerequisites

Before testing, ensure you have:
1. OpenSubtitles API credentials (API key or username/password)
2. Docker and Docker Compose installed
3. All services running (Redis, RabbitMQ, Manager, Downloader)

## Setup

### 1. Configure Credentials

Create/update `.env` file in the project root:

```bash
# Option 1: Using API Key (recommended)
OPENSUBTITLES_API_KEY=your-api-key-here

# Option 2: Using Username/Password (fallback)
OPENSUBTITLES_USERNAME=your-username
OPENSUBTITLES_PASSWORD=your-password

# Optional: Custom configuration
OPENSUBTITLES_API_URL=https://api.opensubtitles.com/api/v1
OPENSUBTITLES_USER_AGENT=get-my-subtitle v1.0
OPENSUBTITLES_MAX_RETRIES=3
OPENSUBTITLES_RETRY_DELAY=1
```

### 2. Install Dependencies

```bash
cd downloader
pip install -r requirements.txt
```

### 3. Start Services

```bash
# Start Redis and RabbitMQ
docker-compose up -d redis rabbitmq

# Or start all services
docker-compose up
```

## Test Scenarios

### Test 1: Successful Subtitle Download (REST API)

**Objective**: Verify subtitle download with API key authentication

**Steps**:
1. Ensure `OPENSUBTITLES_API_KEY` is set in `.env`
2. Start the downloader worker:
   ```bash
   cd downloader
   python worker.py
   ```
3. In another terminal, submit a subtitle request via Manager API:
   ```bash
   curl -X POST http://localhost:8000/api/v1/subtitles/request \
     -H "Content-Type: application/json" \
     -d '{
       "video_title": "The Matrix",
       "imdb_id": "tt0133093",
       "language": "en"
     }'
   ```

**Expected Results**:
- ✅ Downloader logs show: "Authenticated with OpenSubtitles REST API"
- ✅ Downloader logs show: "Found X subtitle(s)"
- ✅ Downloader logs show: "Downloaded subtitle to /path/to/subtitle.srt"
- ✅ Subtitle file exists in storage directory
- ✅ SUBTITLE_READY event published

**Logs to Check**:
```
🔌 Connecting to OpenSubtitles API...
✅ Authenticated with OpenSubtitles REST API
✅ OpenSubtitles client connected using rest method
🔍 Searching for subtitles: title=The Matrix, imdb_id=tt0133093, language=en
✅ Found 10 subtitle(s)
✅ Downloaded subtitle to /storage/subtitles/12345.srt
✅ Subtitle downloaded! Published SUBTITLE_READY event
```

---

### Test 2: Fallback to XML-RPC Authentication

**Objective**: Verify fallback to username/password when API key fails

**Steps**:
1. Set invalid API key and valid username/password in `.env`:
   ```bash
   OPENSUBTITLES_API_KEY=invalid-key
   OPENSUBTITLES_USERNAME=your-username
   OPENSUBTITLES_PASSWORD=your-password
   ```
2. Start the downloader worker
3. Submit a subtitle request

**Expected Results**:
- ⚠️  Downloader logs show: "REST API authentication failed, trying XML-RPC fallback"
- ✅ Downloader logs show: "Authenticated with OpenSubtitles XML-RPC API"
- ✅ Subtitle download proceeds normally

**Logs to Check**:
```
⚠️  REST API authentication failed: Invalid API key, trying XML-RPC fallback
✅ Authenticated with OpenSubtitles XML-RPC API
✅ OpenSubtitles client connected using xmlrpc method
```

---

### Test 3: Subtitle Not Found

**Objective**: Verify fallback to translation when subtitle not found

**Steps**:
1. Submit request for obscure/non-existent movie:
   ```bash
   curl -X POST http://localhost:8000/api/v1/subtitles/request \
     -H "Content-Type: application/json" \
     -d '{
       "video_title": "Nonexistent Movie XYZ123",
       "language": "he"
     }'
   ```

**Expected Results**:
- ⚠️  Downloader logs show: "No subtitle found for job {id}, requesting translation"
- ✅ SUBTITLE_TRANSLATE_REQUESTED event published
- ✅ Payload includes `"reason": "subtitle_not_found"`

**Logs to Check**:
```
🔍 Searching for subtitles: title=Nonexistent Movie XYZ123, language=he
⚠️  No subtitle found for job {id}, requesting translation
📤 Published SUBTITLE_TRANSLATE_REQUESTED event
```

---

### Test 4: Rate Limit Handling

**Objective**: Verify rate limit error handling

**Steps**:
1. Submit multiple requests rapidly (>40 in 10 seconds)
2. Monitor logs for rate limit errors

**Expected Results**:
- ⚠️  Downloader logs show: "Rate limit exceeded"
- ✅ JOB_FAILED event published with `"error_type": "rate_limit"`
- ✅ Error message: "OpenSubtitles rate limit exceeded, please try again later"

**Logs to Check**:
```
⚠️  Rate limit exceeded: Rate limit exceeded
📤 Published JOB_FAILED event with rate_limit error
```

---

### Test 5: API Error Fallback

**Objective**: Verify fallback to translation on API errors

**Steps**:
1. Temporarily set invalid credentials to trigger API errors
2. Submit a subtitle request

**Expected Results**:
- ❌ Downloader logs show: "OpenSubtitles API error"
- ⚠️  Downloader logs show: "Falling back to translation"
- ✅ SUBTITLE_TRANSLATE_REQUESTED event published
- ✅ Payload includes `"reason": "api_error"`

**Logs to Check**:
```
❌ OpenSubtitles API error: [error details]
⚠️  Falling back to translation for job {id}
📤 Published SUBTITLE_TRANSLATE_REQUESTED event
```

---

### Test 6: Token Expiration and Refresh

**Objective**: Verify automatic token refresh on expiration

**Steps**:
1. Start worker and wait for token to approach expiration (typically 24 hours)
2. Or manually test by mocking expired token
3. Submit subtitle request

**Expected Results**:
- ⚠️  Downloader logs show: "Token expired, re-authenticating..."
- ✅ New authentication successful
- ✅ Request retried with new token
- ✅ Subtitle download succeeds

---

### Test 7: Retry Logic

**Objective**: Verify retry with exponential backoff on transient errors

**Steps**:
1. Temporarily disconnect network or block OpenSubtitles API
2. Submit subtitle request
3. Restore network connection

**Expected Results**:
- ⚠️  First attempt fails
- 🔄 Automatic retry after delay
- ✅ Eventually succeeds or fails after 3 attempts
- ✅ Exponential backoff (1s, 2s, 4s delays)

---

## Verification Checklist

After completing all tests, verify:

- [ ] REST API authentication works with API key
- [ ] XML-RPC fallback works with username/password
- [ ] Subtitles are downloaded and saved to storage
- [ ] SUBTITLE_READY events published correctly
- [ ] Translation fallback works when subtitle not found
- [ ] Rate limit errors handled gracefully
- [ ] API errors trigger translation fallback
- [ ] Token refresh works on expiration
- [ ] Retry logic works with exponential backoff
- [ ] No credentials logged in plain text
- [ ] All error scenarios handled without crashes

## Troubleshooting

### Issue: Authentication fails with valid credentials

**Solution**:
- Check if API key/username is correct
- Verify OpenSubtitles account is active
- Check if API URL is correct
- Review rate limits on account

### Issue: Subtitles not downloading

**Solution**:
- Check storage directory permissions
- Verify `SUBTITLE_STORAGE_PATH` in config
- Check available disk space
- Review OpenSubtitles API logs for errors

### Issue: Worker crashes on startup

**Solution**:
- Verify all dependencies installed: `pip install -r requirements.txt`
- Check Redis and RabbitMQ are running
- Review worker logs for specific errors
- Verify environment variables are set

## Performance Testing

### Metrics to Monitor

1. **Response Time**: < 5 seconds for search
2. **Success Rate**: > 90% for popular movies
3. **Error Rate**: < 5% for valid requests
4. **Retry Success**: > 80% after transient failures

### Load Testing

```bash
# Submit 10 concurrent requests
for i in {1..10}; do
  curl -X POST http://localhost:8000/api/v1/subtitles/request \
    -H "Content-Type: application/json" \
    -d "{\"video_title\": \"Movie $i\", \"language\": \"en\"}" &
done
wait
```

**Expected Results**:
- All requests processed
- No crashes or deadlocks
- Rate limiting handled gracefully
- Appropriate error messages

## Notes

- OpenSubtitles has rate limits: 40 requests/10 seconds (authenticated)
- API key is recommended over username/password
- Token typically expires after 24 hours
- Retry logic uses exponential backoff: 1s, 2s, 4s
- Maximum 3 retry attempts before failing

