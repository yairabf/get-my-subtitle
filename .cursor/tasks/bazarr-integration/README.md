# Bazarr Integration Epic

**Status:** Planning  
**Created:** December 8, 2025  
**Last Updated:** December 8, 2025

## Epic Overview

Integrate Bazarr subtitle management system to leverage its 20+ subtitle provider aggregation while adding AI-powered translation capabilities. This enables users to automatically receive subtitles in their desired language (Hebrew) even when only secondary languages (English/Spanish) are available from providers.

## Business Value

**Problem Statement:**
Users with Hebrew as their primary language struggle to find Hebrew subtitles, as most providers primarily offer English and Spanish. Bazarr excels at finding and downloading subtitles across 20+ providers, but lacks translation capabilities.

**Solution:**
Integrate Bazarr as the subtitle discovery engine and use our AI-powered translation service to automatically translate English/Spanish subtitles to Hebrew. This provides users with:
- ✅ Access to 20+ subtitle providers (via Bazarr)
- ✅ Automatic translation to desired language (via our service)
- ✅ Zero manual intervention
- ✅ Both original and translated subtitles available

**User Story:**
> As a user with Hebrew as my primary language, when Bazarr downloads a subtitle in English or Spanish (because Hebrew isn't available), I want the system to automatically translate it to Hebrew, so I can watch media in my preferred language without manual intervention.

## Architecture Strategy

### Core Principle: Source-Agnostic Workers

**Manager as Adapter Layer:**
- Receives source-specific inputs (Bazarr webhook, Jellyfin webhook, API calls, etc.)
- Normalizes all inputs to standard formats (SubtitleResponse, Events, Tasks)
- Workers remain completely agnostic to subtitle source

**Benefits:**
- ✅ Single Responsibility: Manager adapts, Workers process
- ✅ Easy Testing: Mock standard formats, not source-specific data
- ✅ Extensible: Add new sources without modifying workers
- ✅ Maintainable: Changes to one source don't affect others

### Integration Approach

```
┌─────────────────────────────────────────────────────┐
│  Bazarr (External System)                          │
│  - Monitors media library (Sonarr/Radarr)          │
│  - Searches 20+ subtitle providers                 │
│  - Downloads subtitles (Hebrew > English > Spanish) │
└────────────────┬────────────────────────────────────┘
                 │
                 │ Webhook Notification
                 ↓
┌─────────────────────────────────────────────────────┐
│  Our Service - Manager (Adapter Layer)             │
│  - Receives Bazarr webhook                         │
│  - Normalizes to standard format                   │
│  - Publishes standard events                       │
│  - Enqueues standard tasks                         │
└────────────────┬────────────────────────────────────┘
                 │
                 │ Standard Format
                 ↓
┌─────────────────────────────────────────────────────┐
│  Workers (Source-Agnostic)                         │
│  - Translation Worker: Translates EN/ES → Hebrew   │
│  - Consumer Worker: Updates job state              │
│  - (Don't know about Bazarr)                       │
└─────────────────────────────────────────────────────┘
```

## Epic Breakdown: Phases & Tasks

### Phase 1: Webhook Integration (MVP) - 2-3 Weeks
**Goal:** Receive Bazarr webhooks and trigger automatic translation

#### Task 001: Bazarr Webhook Handler
**Status:** Planning  
**Priority:** P0 (Critical)  
**Estimated Effort:** 1-2 weeks

**Deliverables:**
- `POST /webhooks/bazarr` endpoint in Manager
- `BazarrWebhookPayload` schema
- Event normalization to `SUBTITLE_TRANSLATE_REQUESTED`
- Task normalization to `TranslationTask`
- Comprehensive unit tests (TDD)
- Integration tests with real Bazarr
- Documentation

**Success Criteria:**
- Webhook receives Bazarr notifications
- Creates standard Redis job
- Publishes standard event
- Enqueues standard translation task
- Translation Worker processes (agnostic to source)
- Hebrew subtitle created successfully

**Dependencies:**
- Bazarr deployed and configured
- Existing translation service working
- Redis and RabbitMQ healthy

---

### Phase 2: Enhanced Provider Support (Future) - 2-3 Weeks
**Goal:** Use Bazarr as an additional subtitle provider alongside OpenSubtitles

#### Task 002: Bazarr Client Provider
**Status:** Not Started  
**Priority:** P1 (High)  
**Estimated Effort:** 2 weeks

**Deliverables:**
- `BazarrClient` class in downloader service
- Search subtitles via Bazarr API
- Download subtitles via Bazarr API
- Provider priority configuration
- Fallback logic: OpenSubtitles → Bazarr
- Unit tests for BazarrClient
- Integration tests

**Success Criteria:**
- Downloader can search via Bazarr API
- Provider selection based on configuration
- Quality scoring integration
- Automatic fallback on provider failure

**Dependencies:**
- Task 001 completed
- Bazarr API documentation reviewed
- Provider abstraction layer designed

---

### Phase 3: Media Folder Synchronization (Enhancement) - 1 Week
**Goal:** Automatically place translated subtitles next to media files

#### Task 003: Media Folder Sync
**Status:** Not Started  
**Priority:** P2 (Medium)  
**Estimated Effort:** 1 week

**Deliverables:**
- Consumer Worker enhancement
- Copy translated subtitle to media folder
- Metadata tracking for Bazarr-origin jobs
- File naming convention matching
- Tests for file placement

**Success Criteria:**
- Translated subtitle appears next to media file
- Jellyfin/Plex automatically detects it
- Both original and translated subtitles available
- No file conflicts or overwrites

**Dependencies:**
- Task 001 completed
- File permission access verified
- Volume mount configuration documented

---

## Timeline

```
Week 1-2:  Task 001 - Bazarr Webhook Handler (TDD, Implementation, Testing)
Week 3:    Task 001 - Integration Testing, Documentation, Deployment
Week 4-5:  Task 002 - Bazarr Client Provider (Design, TDD, Implementation)
Week 6:    Task 002 - Testing, Documentation
Week 7:    Task 003 - Media Folder Sync (Implementation, Testing)
Week 8:    Final Integration Testing, Production Deployment
```

**MVP Delivery:** Week 3 (Task 001 complete)  
**Full Feature Set:** Week 8 (All tasks complete)

## Configuration Requirements

### Bazarr Configuration
```yaml
# Bazarr Settings > Languages
Language Profile:
  Name: Hebrew-EN-ES
  Languages:
    - Hebrew (he) [Primary - Cutoff]
    - English (en) [Secondary]
    - Spanish (es) [Tertiary]

# Bazarr Settings > Notifications > Webhook
Webhook:
  URL: http://get-my-subtitle-manager:8000/webhooks/bazarr
  Events:
    - On Movie Subtitle Download
    - On Series Subtitle Download
  Headers:
    X-Bazarr-Secret: your-secret-token
```

### Our Service Configuration
```env
# Subtitle Language Preferences
SUBTITLE_DESIRED_LANGUAGE=he              # Hebrew (primary)
SUBTITLE_FALLBACK_LANGUAGE=en             # English (secondary)

# Bazarr Integration
BAZARR_ENABLED=true
BAZARR_WEBHOOK_SECRET=your-secret-token
BAZARR_SAVE_ORIGINAL=true

# Translation Service (Existing)
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL=gpt-4o-mini
TRANSLATION_PARALLEL_REQUESTS=3
```

## Risk Assessment

### High Risk
- **Bazarr Webhook Format Changes**: Bazarr updates may break webhook payload
  - **Mitigation**: Schema validation, comprehensive error handling, monitoring

### Medium Risk
- **File Path Access**: Service needs access to Bazarr's subtitle storage
  - **Mitigation**: Docker volume mounts, path validation, permission checks
  
- **Webhook Security**: Unauthorized webhook submissions
  - **Mitigation**: Webhook secret validation, rate limiting

### Low Risk
- **Performance**: Webhook response time slow under load
  - **Mitigation**: Async processing, background tasks, monitoring

## Success Metrics

### Technical Metrics
- Webhook success rate > 99%
- Webhook response time < 200ms
- Translation success rate > 95%
- Zero impact on existing workflows

### User Metrics
- Number of subtitles auto-translated per day
- Languages translated: English/Spanish → Hebrew
- User satisfaction with subtitle availability

### System Health
- No increase in error rates
- No performance degradation
- Translation Worker remains agnostic
- All tests passing (unit + integration)

## Testing Strategy

### Unit Tests
- Each task includes comprehensive unit tests (TDD approach)
- Target: 90%+ code coverage for new code
- Mock external dependencies (Bazarr, Redis, RabbitMQ)

### Integration Tests
- Real Bazarr instance in Docker
- Full workflow testing: Webhook → Translation → File saved
- Error scenario testing

### End-to-End Tests
- Deploy full stack (Bazarr + our services)
- Simulate real user workflow
- Verify subtitle availability in media player

### Manual Testing
- Test with real media files
- Verify both original and translated subtitles
- Test error recovery scenarios

## Documentation Deliverables

### Technical Documentation
- [ ] Epic README (this file)
- [ ] Task plan for each phase
- [ ] Task summary after completion
- [ ] API documentation for webhook endpoint
- [ ] Integration guide (Bazarr setup)
- [ ] Troubleshooting guide

### User Documentation
- [ ] Configuration guide
- [ ] Quick start guide
- [ ] FAQ
- [ ] Video walkthrough (optional)

## Dependencies

### External Systems
- **Bazarr**: Version 1.0+ with webhook support
- **Sonarr/Radarr**: Optional, for library management
- **Jellyfin/Plex/Emby**: Optional, for media playback

### Our Services
- Manager Service (API + Orchestrator)
- Translation Worker
- Consumer Worker
- Redis (job storage)
- RabbitMQ (event bus)

### Infrastructure
- Docker / Docker Compose
- Shared volume access between Bazarr and our service
- Network connectivity for webhooks

## Future Considerations

### Phase 4+ Enhancements (Not Planned Yet)
- Multi-language translation (Hebrew + English)
- Quality scoring integration from Bazarr
- Bidirectional sync (our service → Bazarr)
- Analytics dashboard for provider success rates
- Webhook events for translation completion → Bazarr
- Automatic subtitle upgrade when better version available

## Related Documentation

- [Main Project README](../../../README.md)
- [Manager Service Documentation](../../../src/manager/README.md)
- [Translation Service Documentation](../../../src/translator/README.md)
- [Event-Driven Architecture](../../docs/EVENT_DRIVEN_ARCHITECTURE.md)

## Questions & Decisions Log

### Decision 1: Webhook vs Polling
**Question:** Should we poll Bazarr API or use webhooks?  
**Decision:** Webhooks (real-time, better UX)  
**Rationale:** Immediate response when subtitle downloaded, no polling overhead

### Decision 2: Where to Save Translated Files?
**Question:** Save in standard storage or directly to media folder?  
**Decision:** Phase 1 uses standard storage, Phase 3 adds media folder copy  
**Rationale:** Keeps Translation Worker agnostic, media folder as enhancement

### Decision 3: Keep Original Subtitle?
**Question:** Delete or keep original after translation?  
**Decision:** Keep both (configurable via `BAZARR_SAVE_ORIGINAL`)  
**Rationale:** Users may want both languages, flexibility is valuable

### Decision 4: Webhook Security?
**Question:** Require webhook secret or make it optional?  
**Decision:** Optional but recommended  
**Rationale:** Easier initial setup, security as enhancement

## Contact & Support

**Epic Owner:** Development Team  
**Stakeholders:** Users with non-English primary language  
**Review Required:** Architecture team (for source-agnostic design)

---

**Last Updated:** December 8, 2025  
**Next Review:** After Task 001 completion

