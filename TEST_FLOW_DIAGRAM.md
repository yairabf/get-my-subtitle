# Test Flow Diagrams

Visual representations of what you're testing and how it works.

---

## Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                            YOUR TESTING                              │
│                                                                       │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐      │
│  │  Submit Job  │ ───> │  Watch Job   │ ───> │ Check Events │      │
│  │  (curl POST) │      │  (curl GET)  │      │  (curl GET)  │      │
│  └──────────────┘      └──────────────┘      └──────────────┘      │
│         │                      │                      │              │
└─────────┼──────────────────────┼──────────────────────┼──────────────┘
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       MANAGER API (Port 8000)                        │
│                                                                       │
│  POST /subtitles/download  │  GET /status  │  GET /events           │
└─────────────────────────────────────────────────────────────────────┘
          │                                              ▲
          │ Creates Job                                  │ Reads Events
          ▼                                              │
┌─────────────────────────────────────────────────────────────────────┐
│                       REDIS (Port 6379)                              │
│                                                                       │
│  ┌──────────────────┐         ┌──────────────────────────────┐     │
│  │  Job Data        │         │  Event History               │     │
│  │  job:{id}        │         │  job:events:{id}             │     │
│  │  - status        │         │  - [event1, event2, ...]     │     │
│  │  - video_url     │         │                              │     │
│  │  - language      │         │                              │     │
│  └──────────────────┘         └──────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
          │                                              ▲
          │ Enqueues Task                                │ Updates State
          ▼                                              │
┌─────────────────────────────────────────────────────────────────────┐
│                    RABBITMQ (Ports 5672, 15672)                      │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Exchange: subtitle.events (topic)                            │  │
│  │                                                                │  │
│  │  Routing Keys:                                                │  │
│  │  - subtitle.download.requested                                │  │
│  │  - subtitle.ready                                             │  │
│  │  - subtitle.translate.requested                               │  │
│  │  - subtitle.translated                                        │  │
│  │  - job.failed                                                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
│          │                    │                    │                 │
│          │                    │                    │                 │
│  ┌───────▼────────────────────▼────────────────────▼─────────────┐ │
│  │  Queue: subtitle.events.consumer                              │ │
│  │  Bindings: subtitle.*, job.*                                  │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
          │                    │                    │
          │                    │                    │
    ┌─────▼─────┐       ┌──────▼──────┐      ┌────▼──────┐
    │           │       │             │      │           │
    │ Downloader│       │ Translator  │      │ Consumer  │
    │  Worker   │       │   Worker    │      │  Service  │
    │           │       │             │      │           │
    └───────────┘       └─────────────┘      └───────────┘
         │                     │                    │
         │ Publishes           │ Publishes          │ Processes
         │ Events              │ Events             │ Events
         │                     │                    │
         └─────────────────────┴────────────────────┘
                           │
                           ▼
                    Updates Redis State
```

---

## Test Flow 1: Subtitle Found (90% probability)

```
YOU                MANAGER         REDIS           RABBITMQ        DOWNLOADER      CONSUMER
 │                   │               │                │               │               │
 │ POST /download    │               │                │               │               │
 ├──────────────────>│               │                │               │               │
 │                   │               │                │               │               │
 │                   │ Create Job    │                │               │               │
 │                   ├──────────────>│                │               │               │
 │                   │ status:       │                │               │               │
 │                   │ QUEUED        │                │               │               │
 │                   │               │                │               │               │
 │<──────────────────┤               │                │               │               │
 │ {job_id, QUEUED}  │               │                │               │               │
 │                   │               │                │               │               │
 │                   │ Publish       │                │               │               │
 │                   │ download      │                │               │               │
 │                   │ requested     │                │               │               │
 │                   ├───────────────┴───────────────>│               │               │
 │                   │               │                │               │               │
 │                   │               │                │ Consume Task  │               │
 │                   │               │                ├──────────────>│               │
 │                   │               │                │               │               │
 │                   │               │                │               │ Update Status │
 │                   │               │<───────────────┴───────────────┤ IN_PROGRESS   │
 │                   │               │                │               │               │
 │ GET /status       │               │                │               │               │
 ├──────────────────>│ Get Status    │                │               │               │
 │                   ├──────────────>│                │               │               │
 │<──────────────────┤ IN_PROGRESS   │                │               │               │
 │ IN_PROGRESS       │               │                │               │               │
 │                   │               │                │               │ Download OK   │
 │                   │               │                │               │               │
 │                   │               │                │               │ Publish       │
 │                   │               │                │               │ subtitle.ready│
 │                   │               │                │<──────────────┤               │
 │                   │               │                │               │               │
 │                   │               │                │ Consume Event │               │
 │                   │               │                ├───────────────┴──────────────>│
 │                   │               │                │                               │
 │                   │               │                │               Update Status   │
 │                   │               │<───────────────┴───────────────────────────────┤
 │                   │               │                │               status: DONE    │
 │                   │               │                │               Record Event    │
 │                   │               │                │                               │
 │ GET /status       │               │                │                               │
 ├──────────────────>│ Get Status    │                │                               │
 │                   ├──────────────>│                │                               │
 │<──────────────────┤ DONE          │                │                               │
 │ DONE ✓            │               │                │                               │
 │                   │               │                │                               │
 │ GET /events       │               │                │                               │
 ├──────────────────>│ Get Events    │                │                               │
 │                   ├──────────────>│                │                               │
 │<──────────────────┤ [events]      │                │                               │
 │ [2 events] ✓      │               │                │                               │
```

**Timeline:**
- t=0s: Job submitted
- t=1s: Status = DOWNLOAD_IN_PROGRESS
- t=2s: Status = DONE
- t=3s: Events = 2 (download.requested, subtitle.ready)

---

## Test Flow 2: Subtitle Not Found → Translation (10% probability)

```
YOU                MANAGER         REDIS           RABBITMQ        DOWNLOADER    TRANSLATOR    CONSUMER
 │                   │               │                │               │              │              │
 │ POST /download    │               │                │               │              │              │
 ├──────────────────>│               │                │               │              │              │
 │                   │               │                │               │              │              │
 │                   │ Create Job    │                │               │              │              │
 │                   ├──────────────>│                │               │              │              │
 │<──────────────────┤ QUEUED        │                │               │              │              │
 │ {job_id, QUEUED}  │               │                │               │              │              │
 │                   │               │                │               │              │              │
 │                   │ Publish       │                │               │              │              │
 │                   ├───────────────┴───────────────>│               │              │              │
 │                   │               │                │               │              │              │
 │                   │               │                │ Consume       │              │              │
 │                   │               │                ├──────────────>│              │              │
 │                   │               │                │               │              │              │
 │                   │               │<───────────────┴───────────────┤              │              │
 │                   │               │ status: IN_PROGRESS            │              │              │
 │                   │               │                │               │              │              │
 │                   │               │                │               │ Subtitle     │              │
 │                   │               │                │               │ NOT FOUND    │              │
 │                   │               │                │               │              │              │
 │                   │               │                │               │ Publish      │              │
 │                   │               │                │               │ translate    │              │
 │                   │               │                │               │ requested    │              │
 │                   │               │                │<──────────────┤              │              │
 │                   │               │                │               │              │              │
 │                   │               │                │ Consume Event │              │              │
 │                   │               │                ├───────────────┴──────────────┴─────────────>│
 │                   │               │                │                              │              │
 │                   │               │<───────────────┴──────────────────────────────┴──────────────┤
 │                   │               │ status: TRANSLATE_QUEUED                     Record Event    │
 │                   │               │                │                              │              │
 │ GET /status       │               │                │                              │              │
 ├──────────────────>│               │                │                              │              │
 │<──────────────────┤               │                │                              │              │
 │ TRANSLATE_QUEUED  │               │                │                              │              │
 │                   │               │                │               Consume Task   │              │
 │                   │               │                ├──────────────────────────────>│              │
 │                   │               │                │                              │              │
 │                   │               │<───────────────┴──────────────────────────────┤              │
 │                   │               │ status: TRANSLATE_IN_PROGRESS                 │              │
 │                   │               │                │                              │              │
 │                   │               │                │                              │ Translate    │
 │                   │               │                │                              │ Complete     │
 │                   │               │                │                              │              │
 │                   │               │                │                              │ Publish      │
 │                   │               │                │<─────────────────────────────┤ translated   │
 │                   │               │                │                              │              │
 │                   │               │                │ Consume Event                │              │
 │                   │               │                ├──────────────────────────────┴──────────────>│
 │                   │               │                │                                             │
 │                   │               │<───────────────┴─────────────────────────────────────────────┤
 │                   │               │ status: DONE                                  Record Event   │
 │                   │               │                │                                             │
 │ GET /status       │               │                │                                             │
 ├──────────────────>│               │                │                                             │
 │<──────────────────┤ DONE ✓        │                │                                             │
 │                   │               │                │                                             │
 │ GET /events       │               │                │                                             │
 ├──────────────────>│               │                │                                             │
 │<──────────────────┤ [3 events] ✓  │                │                                             │
```

**Timeline:**
- t=0s: Job submitted
- t=1s: Status = DOWNLOAD_IN_PROGRESS
- t=2s: Subtitle not found
- t=3s: Status = TRANSLATE_QUEUED
- t=4s: Status = TRANSLATE_IN_PROGRESS
- t=7s: Status = DONE
- t=8s: Events = 3 (download.requested, translate.requested, translated)

---

## Event History Structure

```
GET /subtitles/{job_id}/events

Response:
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_count": 3,
  "events": [
    {
      "event_type": "subtitle.translated",      ← Most Recent
      "timestamp": "2025-10-29T10:10:00Z",
      "source": "translator",
      "payload": {
        "job_id": "550e8400-...",
        "source_language": "en",
        "target_language": "he"
      },
      "metadata": {}
    },
    {
      "event_type": "subtitle.translate.requested",
      "timestamp": "2025-10-29T10:09:30Z",
      "source": "downloader",
      "payload": {
        "job_id": "550e8400-...",
        "reason": "subtitle_not_found"
      },
      "metadata": {}
    },
    {
      "event_type": "subtitle.download.requested",  ← Oldest
      "timestamp": "2025-10-29T10:09:00Z",
      "source": "manager",
      "payload": {
        "job_id": "550e8400-...",
        "video_url": "https://example.com/video.mp4",
        "language": "he"
      },
      "metadata": {}
    }
  ]
}
```

---

## RabbitMQ Event Routing

```
                    subtitle.events (topic exchange)
                              │
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        │                     │                     │
  Routing Key:          Routing Key:         Routing Key:
  subtitle.*            job.*                test.*
        │                     │                     │
        │                     │                     │
        └─────────────────────┴─────────────────────┘
                              │
                              ▼
                subtitle.events.consumer (queue)
                              │
                              │
                        ┌─────┴─────┐
                        │           │
                    Consumer    Consumer
                    Instance 1  Instance 2
                    (if scaled)
```

**Event Types & Routing:**
- `subtitle.download.requested` → Matches `subtitle.*`
- `subtitle.ready` → Matches `subtitle.*`
- `subtitle.translate.requested` → Matches `subtitle.*`
- `subtitle.translated` → Matches `subtitle.*`
- `job.failed` → Matches `job.*`

---

## Redis Data Structure

```
Redis Keys:

job:{job_id}                          ← Job metadata
└─ JSON: {
     job_id: UUID,
     status: enum,
     video_url: string,
     video_title: string,
     language: string,
     created_at: timestamp,
     updated_at: timestamp,
     metadata: {...}
   }

job:events:{job_id}                   ← Event history (list)
└─ LIST: [
     {event_type, timestamp, source, payload},  ← Most recent
     {event_type, timestamp, source, payload},
     {event_type, timestamp, source, payload}   ← Oldest
   ]

task:queue:download                   ← Download tasks (list)
└─ LIST: [task1, task2, ...]

task:queue:translate                  ← Translation tasks (list)
└─ LIST: [task1, task2, ...]
```

---

## Status Transitions

```
DOWNLOAD_QUEUED ──────────> DOWNLOAD_IN_PROGRESS
                                     │
                                     │
                    ┌────────────────┴────────────────┐
                    │                                 │
                    │                                 │
              Subtitle Found               Subtitle Not Found
                    │                                 │
                    ▼                                 ▼
                  DONE                      TRANSLATE_QUEUED
                                                     │
                                                     ▼
                                          TRANSLATE_IN_PROGRESS
                                                     │
                                                     ▼
                                                   DONE

                            Any Stage
                                │
                                │ Error
                                ▼
                            FAILED
```

---

## Testing Verification Points

### ✅ What to Check at Each Step

**After Job Submission:**
- [ ] Job ID returned
- [ ] Status = DOWNLOAD_QUEUED
- [ ] Job exists in Redis
- [ ] Event published to RabbitMQ

**During Processing:**
- [ ] Status updates correctly
- [ ] Events published for each stage
- [ ] Consumer receives events
- [ ] Redis updated by consumer

**After Completion:**
- [ ] Final status = DONE (or FAILED)
- [ ] All events recorded in order
- [ ] Event count matches expected
- [ ] TTL set on Redis keys

**RabbitMQ:**
- [ ] Exchange exists
- [ ] Queue has consumer
- [ ] Messages flowing
- [ ] Bindings correct

**Redis:**
- [ ] Job data complete
- [ ] Event history populated
- [ ] Correct data types
- [ ] TTL configured

---

## Performance Metrics

### Expected Timing

**Subtitle Found Flow:**
- Job submission: < 100ms
- Status update (queued → in_progress): ~1s
- Download completion: ~2-3s
- Event processing: < 500ms
- **Total: ~3-4 seconds**

**Translation Flow:**
- Job submission: < 100ms
- Download attempt: ~2s
- Translation queued: ~500ms
- Translation processing: ~3-5s
- Event processing: < 500ms
- **Total: ~6-8 seconds**

### Load Testing

**5 Concurrent Jobs:**
- All should complete within 10 seconds
- No queue backlog
- No errors

**10 Concurrent Jobs:**
- All should complete within 15 seconds
- Minimal queue backlog
- No errors

---

## Common Issues & Solutions

### Issue: Job Stuck in QUEUED
**Check:** Worker logs, RabbitMQ queue depth
**Solution:** Restart workers

### Issue: Events Not Recording
**Check:** Consumer logs, RabbitMQ bindings
**Solution:** Restart consumer, verify exchange

### Issue: Redis Connection Errors
**Check:** Redis health, connection string
**Solution:** Restart Redis, check .env

### Issue: RabbitMQ Connection Errors
**Check:** RabbitMQ health, credentials
**Solution:** Restart RabbitMQ, check .env

---

## Next Steps

1. ✅ Start services
2. ✅ Run health check
3. ✅ Submit test job
4. ✅ Watch progress
5. ✅ Verify events
6. ✅ Check all systems
7. ✅ Run load test
8. 🎉 Celebrate!

**Ready to test? Start with:**
```bash
./scripts/test_manual.sh help
```

