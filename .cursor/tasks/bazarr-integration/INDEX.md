# Bazarr Integration - Documentation Index

**Epic:** Bazarr Integration  
**Status:** Planning Phase  
**Created:** December 8, 2025

## 📚 Quick Navigation

### 🎯 Getting Started
1. **[Quick Start Guide](./QUICK_START.md)** ⭐ START HERE
   - Fast-track implementation guide
   - Step-by-step checklist
   - Common commands
   - Estimated time: 2-3 weeks

2. **[Epic README](./README.md)**
   - Epic overview and business value
   - Architecture strategy
   - All phases and tasks breakdown
   - Timeline and dependencies

### 📖 Detailed Documentation

3. **[Technical Guide](./TECHNICAL_GUIDE.md)**
   - Complete architecture details
   - Event flow diagrams
   - Data transformation pipeline
   - Configuration guide
   - Troubleshooting

### 📋 Task Plans (Phases)

#### Phase 1: Webhook Integration (MVP) - CURRENT
**[Task 001: Bazarr Webhook Handler](./001-bazarr-webhook-handler/001-bazarr-webhook-handler_plan.mdc)**
- **Priority:** P0 (Critical)
- **Effort:** 1-2 weeks
- **Status:** Planning
- **Deliverables:**
  - Webhook endpoint: `POST /webhooks/bazarr`
  - Event normalization to standard format
  - Translation trigger for EN/ES → Hebrew
  - Comprehensive tests + documentation

#### Phase 2: Provider Integration (Future)
**[Task 002: Bazarr Client Provider](./002-bazarr-client-provider/002-bazarr-client-provider_plan.mdc)**
- **Priority:** P1 (High)
- **Effort:** 2 weeks
- **Status:** Not Started
- **Deliverables:**
  - BazarrClient for API integration
  - Provider selection and fallback logic
  - Quality scoring integration

#### Phase 3: Media Folder Sync (Enhancement)
**[Task 003: Media Folder Sync](./003-media-folder-sync/003-media-folder-sync_plan.mdc)**
- **Priority:** P2 (Medium)
- **Effort:** 1 week
- **Status:** Not Started
- **Deliverables:**
  - Auto-copy translated subtitles to media folder
  - File naming convention matching
  - Media player integration

---

## 🎯 Implementation Path

### For First-Time Implementation

```
1. Read: Quick Start Guide (QUICK_START.md)
   ↓
2. Review: Epic README for context
   ↓
3. Deploy: Bazarr (Docker)
   ↓
4. Configure: Bazarr language profile + webhook
   ↓
5. Implement: Task 001 (TDD approach)
   ↓
6. Test: Integration and manual testing
   ↓
7. Document: Create summary document
   ↓
8. Optional: Tasks 002 and 003
```

### For Review/Reference

```
Need architecture details? → Technical Guide
Need configuration help? → Technical Guide > Configuration
Need troubleshooting? → Technical Guide > Troubleshooting
Need task details? → Specific task plan (001/002/003)
Need quick commands? → Quick Start Guide
```

---

## 📁 File Structure

```
.cursor/tasks/bazarr-integration/
├── INDEX.md                              ← You are here
├── README.md                             ← Epic overview
├── QUICK_START.md                        ← Fast implementation guide
├── TECHNICAL_GUIDE.md                    ← Deep technical details
│
├── 001-bazarr-webhook-handler/          ← Phase 1 (MVP)
│   ├── 001-bazarr-webhook-handler_plan.mdc
│   └── 001-bazarr-webhook-handler_summary.mdc  (after completion)
│
├── 002-bazarr-client-provider/          ← Phase 2 (Future)
│   ├── 002-bazarr-client-provider_plan.mdc
│   └── 002-bazarr-client-provider_summary.mdc  (after completion)
│
└── 003-media-folder-sync/               ← Phase 3 (Future)
    ├── 003-media-folder-sync_plan.mdc
    └── 003-media-folder-sync_summary.mdc       (after completion)
```

---

## 🔍 Quick Reference

### Key Concepts

| Concept | Description | Reference |
|---------|-------------|-----------|
| **Source-Agnostic Design** | Workers don't know where subtitles came from | [Technical Guide](./TECHNICAL_GUIDE.md#source-agnostic-design) |
| **Event Normalization** | Manager converts all inputs to standard format | [Technical Guide](./TECHNICAL_GUIDE.md#event-flow) |
| **Webhook Handler** | Adapter that receives Bazarr events | [Task 001](./001-bazarr-webhook-handler/001-bazarr-webhook-handler_plan.mdc) |
| **Provider Fallback** | Try OpenSubtitles → Bazarr → Others | [Task 002](./002-bazarr-client-provider/002-bazarr-client-provider_plan.mdc) |
| **Media Folder Sync** | Copy translated files to media directory | [Task 003](./003-media-folder-sync/003-media-folder-sync_plan.mdc) |

### Key Files to Modify

| File | Purpose | Task |
|------|---------|------|
| `src/manager/main.py` | Add webhook endpoint | 001 |
| `src/manager/schemas.py` | Add BazarrWebhookPayload | 001 |
| `src/common/config.py` | Add Bazarr configuration | 001 |
| `tests/manager/test_bazarr_webhook.py` | Unit tests (TDD) | 001 |
| `src/downloader/bazarr_client.py` | Bazarr API client | 002 |
| `src/consumer/worker.py` | Media folder copy | 003 |

### Quick Commands

```bash
# Deploy Bazarr
docker run -d --name=bazarr -p 6767:6767 \
  -v ./bazarr-config:/config \
  -v /path/to/media:/media \
  lscr.io/linuxserver/bazarr:latest

# Run tests (TDD)
pytest tests/manager/test_bazarr_webhook.py -v

# Test webhook manually
curl -X POST http://localhost:8000/webhooks/bazarr \
  -H "Content-Type: application/json" \
  -d '{"event_type":"subtitle_downloaded","language":"en",...}'

# Check Redis job
docker exec -it redis redis-cli GET "subtitle:job:<job_id>"

# Watch logs
docker-compose logs -f manager translator
```

---

## ✅ Task Status Tracking

### Task 001: Bazarr Webhook Handler
- [ ] Planning document created
- [ ] Test file created
- [ ] Schema implemented
- [ ] Endpoint implemented
- [ ] Integration tested
- [ ] Documentation updated
- [ ] Summary document created

### Task 002: Bazarr Client Provider
- [ ] Planning document created
- [ ] Not started yet (depends on Task 001)

### Task 003: Media Folder Sync
- [ ] Planning document created
- [ ] Not started yet (depends on Task 001)

---

## 📊 Progress Tracking

**Overall Epic Progress:**
```
[####------] 40% Planning Complete

Task 001: [###-------] 30% (Planning Phase)
Task 002: [#---------] 10% (Planning Phase)
Task 003: [#---------] 10% (Planning Phase)
```

**Next Milestone:** Task 001 Implementation Start

---

## 🎓 Learning Resources

### Understanding the Architecture
1. Read: [Epic README](./README.md) - Big picture
2. Read: [Technical Guide](./TECHNICAL_GUIDE.md) - Deep dive
3. Review: Existing codebase patterns
4. Study: Event-driven architecture

### Understanding Bazarr
1. Deploy Bazarr and explore UI
2. Configure language profiles
3. Test webhook functionality
4. Review Bazarr API documentation

### TDD Approach
1. Write tests first (should fail)
2. Implement minimal code to pass tests
3. Refactor for quality
4. Repeat

---

## 🤝 Contributing

### Before Starting Implementation

1. ✅ Read Quick Start Guide
2. ✅ Review Epic README
3. ✅ Understand source-agnostic design
4. ✅ Deploy Bazarr for testing
5. ✅ Configure development environment

### During Implementation

1. ✅ Follow TDD approach (tests first)
2. ✅ Keep workers source-agnostic
3. ✅ Use standard event formats
4. ✅ Write comprehensive tests
5. ✅ Document as you go

### After Implementation

1. ✅ Create summary document
2. ✅ Update this INDEX with status
3. ✅ Share learnings with team
4. ✅ Plan next phase

---

## 📞 Support

### Need Help?

1. **Technical Questions:** Review [Technical Guide](./TECHNICAL_GUIDE.md)
2. **Implementation Questions:** Review [Task Plans](./001-bazarr-webhook-handler/)
3. **Troubleshooting:** See [Technical Guide - Troubleshooting](./TECHNICAL_GUIDE.md#troubleshooting)
4. **Quick Answers:** See [Quick Start Guide](./QUICK_START.md)

### Common Questions

**Q: Where do I start?**  
A: [Quick Start Guide](./QUICK_START.md) - Step-by-step implementation

**Q: What's the architecture?**  
A: [Technical Guide - Architecture](./TECHNICAL_GUIDE.md#architecture-overview)

**Q: How long will this take?**  
A: Task 001 (MVP): 2-3 weeks. Full epic: 6-8 weeks.

**Q: What if Bazarr webhook format changes?**  
A: Only affects webhook handler (schema validation). Workers unaffected.

**Q: Can I add other subtitle sources?**  
A: Yes! Manager normalizes all sources. Workers stay the same.

---

## 🚀 Ready to Start?

**Current Phase:** Task 001 - Bazarr Webhook Handler  
**Next Step:** [Quick Start Guide](./QUICK_START.md)  
**Estimated Time:** 2-3 weeks

**Let's build! 🎬**

---

**Last Updated:** December 8, 2025  
**Maintainer:** Development Team  
**Epic Status:** Planning Phase



