# Bazarr Integration - Quick Start Guide

**For:** Developers implementing Bazarr webhook integration  
**Time to Complete:** 2-3 weeks (Task 001)

## 🎯 Goal

Enable automatic translation of English/Spanish subtitles to Hebrew when Bazarr downloads them (because Hebrew subtitles aren't available).

## 📋 Prerequisites

- [ ] Project is running successfully
- [ ] Translation service working (OpenAI configured)
- [ ] Docker and Docker Compose installed
- [ ] Read [Epic README](./README.md)

## 🚀 Quick Start (Task 001)

### Step 1: Deploy Bazarr (5 minutes)

```bash
# Add to docker-compose.yml
docker run -d \
  --name=bazarr \
  -p 6767:6767 \
  -v ./bazarr-config:/config \
  -v /path/to/media:/media \
  lscr.io/linuxserver/bazarr:latest

# Access: http://localhost:6767
```

### Step 2: Configure Bazarr (10 minutes)

**Language Profile:**
1. Settings > Languages > Add Profile
2. Name: `Hebrew-EN-ES`
3. Add languages:
   - Hebrew (he) ⭐ Primary (Cutoff ✓)
   - English (en) 🔄 Secondary
   - Spanish (es) 🔄 Tertiary
4. Save

**Webhook:**
1. Settings > Notifications > Webhook
2. URL: `http://get-my-subtitle-manager:8000/webhooks/bazarr`
3. Events: ✓ On Movie/Series Subtitle Download
4. Headers: `X-Bazarr-Secret: your-secret`
5. Test Webhook (should return 404 initially - we haven't implemented yet)
6. Save

### Step 3: Configure Your Service (5 minutes)

Add to `.env`:
```env
# Bazarr Integration
BAZARR_ENABLED=true
BAZARR_WEBHOOK_SECRET=your-secret
BAZARR_SAVE_ORIGINAL=true

# Language Preferences
SUBTITLE_DESIRED_LANGUAGE=he
SUBTITLE_FALLBACK_LANGUAGE=en
```

### Step 4: Implementation (TDD Approach)

#### Week 1: Tests & Schema (3-4 days)

**Day 1: Create Test File** 📝
```bash
# Create test file
touch tests/manager/test_bazarr_webhook.py

# Write test cases (BEFORE implementation)
# - Test schema validation
# - Test webhook endpoint
# - Test event normalization
# - Test error handling

# Run tests (should fail)
pytest tests/manager/test_bazarr_webhook.py -v
```

**Day 2-3: Implement Schema** 🏗️
```bash
# 1. Add BazarrWebhookPayload to src/manager/schemas.py
# 2. Add Bazarr config to src/common/config.py
# 3. Run schema tests (should pass)
pytest tests/manager/test_bazarr_webhook.py::TestBazarrWebhookPayload -v
```

**Day 4: Implement Endpoint** 🔌
```bash
# 1. Add POST /webhooks/bazarr to src/manager/main.py
# 2. Implement handler logic
# 3. Run endpoint tests (should pass)
pytest tests/manager/test_bazarr_webhook.py::TestBazarrWebhookEndpoint -v
```

#### Week 2: Integration & Testing (4-5 days)

**Day 5-6: Integration Testing** 🧪
```bash
# 1. Start full stack
docker-compose up -d

# 2. Test Bazarr webhook delivery
# In Bazarr UI: Settings > Notifications > Webhook > Test
# Should return 200 OK with job_id

# 3. Add test media file to Bazarr
# 4. Wait for subtitle download
# 5. Verify translation triggered
docker-compose logs -f translator

# 6. Verify Hebrew subtitle created
ls -la storage/subtitles/*.he.srt
```

**Day 7-8: Manual Testing & Fixes** 🐛
```bash
# Test all scenarios:
# - Hebrew subtitle (skip translation)
# - English subtitle (trigger translation)
# - Spanish subtitle (trigger translation)
# - Invalid payload (422 error)
# - File not found (500 error)
# - Permission denied (500 error)
```

**Day 9: Documentation** 📚
```bash
# 1. Update README.md
# 2. Create BAZARR_INTEGRATION.md
# 3. Add configuration examples
# 4. Add troubleshooting guide
# 5. Create summary document
```

#### Week 3: Polish & Deployment (Optional)

**Day 10-12: Optional Enhancements**
- Webhook security (secret validation)
- Performance optimization
- Additional error scenarios
- Metrics/monitoring

**Day 13-15: Production Deployment**
- Deploy to production
- Monitor logs
- Verify webhooks working
- User testing

## 📝 Implementation Checklist

### Phase 1: Tests (TDD) ✅
- [ ] Create `tests/manager/test_bazarr_webhook.py`
- [ ] Write schema validation tests
- [ ] Write endpoint tests
- [ ] Write normalization tests
- [ ] Run tests (should fail) ✓ Expected

### Phase 2: Schema ✅
- [ ] Add `BazarrWebhookPayload` to schemas.py
- [ ] Add Bazarr config to config.py
- [ ] Update .env with Bazarr settings
- [ ] Run schema tests (should pass)

### Phase 3: Endpoint ✅
- [ ] Add `POST /webhooks/bazarr` to main.py
- [ ] Implement webhook handler
- [ ] Normalize to standard format
- [ ] Publish standard event
- [ ] Enqueue standard task
- [ ] Run endpoint tests (should pass)

### Phase 4: Integration ✅
- [ ] Deploy Bazarr + your services
- [ ] Configure Bazarr webhook
- [ ] Test with real media file
- [ ] Verify full workflow
- [ ] Test error scenarios

### Phase 5: Documentation ✅
- [ ] Update README.md
- [ ] Create technical docs
- [ ] Add troubleshooting guide
- [ ] Create summary document

## 🧪 Testing Quick Commands

```bash
# Run all Bazarr webhook tests
pytest tests/manager/test_bazarr_webhook.py -v

# Run specific test class
pytest tests/manager/test_bazarr_webhook.py::TestBazarrWebhookEndpoint -v

# Run with coverage
pytest tests/manager/test_bazarr_webhook.py --cov=src/manager --cov-report=html

# Test webhook manually
curl -X POST http://localhost:8000/webhooks/bazarr \
  -H "Content-Type: application/json" \
  -H "X-Bazarr-Secret: your-secret" \
  -d '{
    "event_type": "subtitle_downloaded",
    "media_type": "movie",
    "media_title": "Test Movie",
    "media_path": "/media/Test.mkv",
    "subtitle_path": "/media/Test.en.srt",
    "language": "en",
    "provider": "opensubtitles",
    "score": 0.95
  }'

# Check job in Redis
docker exec -it redis redis-cli KEYS "subtitle:job:*"

# Check RabbitMQ queue
# Open: http://localhost:15672 (guest/guest)
# Navigate to: Queues > subtitle.translation

# Watch logs
docker-compose logs -f manager
docker-compose logs -f translator
```

## 🐛 Common Issues & Quick Fixes

### Issue: Webhook returns 404

**Fix:**
```bash
# Check endpoint exists
curl http://localhost:8000/docs
# Should see /webhooks/bazarr in API docs

# If not, endpoint not implemented yet
# → Continue with implementation
```

### Issue: Webhook returns 422

**Fix:**
```bash
# Invalid payload format
# Check payload against BazarrWebhookPayload schema
# Required fields: event_type, media_path, subtitle_path, language
```

### Issue: Webhook returns 500

**Fix:**
```bash
# Check logs for detailed error
docker-compose logs manager | tail -50

# Common causes:
# - File not found: Check subtitle_path exists
# - Permission denied: Check volume mounts
# - Redis error: Check Redis is running
# - RabbitMQ error: Check RabbitMQ is running
```

### Issue: Translation not triggered

**Fix:**
```bash
# 1. Check webhook returned success + job_id
# 2. Check Redis for job
docker exec -it redis redis-cli GET "subtitle:job:<job_id>"

# 3. Check RabbitMQ for task
# http://localhost:15672 > Queues > subtitle.translation

# 4. Check translator worker is running
docker-compose ps translator
docker-compose logs -f translator
```

## 📚 Documentation References

- **Epic Overview:** [README.md](./README.md)
- **Task 001 Plan:** [001-bazarr-webhook-handler_plan.mdc](./001-bazarr-webhook-handler/001-bazarr-webhook-handler_plan.mdc)
- **Technical Guide:** [TECHNICAL_GUIDE.md](./TECHNICAL_GUIDE.md)
- **Main Project README:** [../../../README.md](../../../README.md)

## 🎯 Success Metrics

**MVP Complete When:**
- ✅ All unit tests pass (90%+ coverage)
- ✅ Webhook receives Bazarr notifications
- ✅ Hebrew subtitles skip translation
- ✅ English/Spanish subtitles trigger translation
- ✅ Hebrew subtitle file created successfully
- ✅ Documentation complete

**Timeline:**
- **Week 1:** Tests + Schema + Endpoint (5 days)
- **Week 2:** Integration + Testing (5 days)
- **Week 3:** Polish + Deployment (5 days)

**Total:** 2-3 weeks for Task 001 MVP

## 🚀 Next Steps After Task 001

1. **Task 002:** Bazarr Client Provider (use Bazarr API for downloads)
2. **Task 003:** Media Folder Sync (copy translated files to media folder)

---

**Questions?**
- Review [Technical Guide](./TECHNICAL_GUIDE.md)
- Check [Troubleshooting](./TECHNICAL_GUIDE.md#troubleshooting)
- Read [Epic README](./README.md)

**Ready to start?** → Begin with Step 1: Deploy Bazarr! 🎬



