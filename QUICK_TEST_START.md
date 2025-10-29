# Quick Test Start Guide

Get up and running with testing in 5 minutes! 🚀

---

## 1. Prerequisites Check

```bash
# Make sure Docker is running
docker ps

# Check you have the .env file
ls -la .env || cp env.template .env
```

---

## 2. Start Services (30 seconds)

```bash
# Clean start
docker-compose down -v

# Build and start all services
docker-compose up --build -d

# Wait for services to be healthy (30-60 seconds)
sleep 30
```

---

## 3. Verify Health (10 seconds)

```bash
# Quick health check
./scripts/test_manual.sh check-health

# Expected: All services should be healthy ✓
```

---

## 4. Submit Test Job (5 seconds)

```bash
# Submit a test job
./scripts/test_manual.sh submit-job

# You'll see output like:
# {
#   "job_id": "550e8400-e29b-41d4-a716-446655440000",
#   "status": "DOWNLOAD_QUEUED",
#   "message": "Download job queued successfully"
# }
```

---

## 5. Watch Progress (15-30 seconds)

```bash
# Replace with your actual job_id from step 4
./scripts/test_manual.sh watch-job <job_id>

# This will show status updates every 2 seconds:
# 10:04:58: Status = DOWNLOAD_QUEUED
# 10:04:59: Status = DOWNLOAD_IN_PROGRESS
# 10:05:00: Status = DONE ✓
```

---

## 6. Check Results (5 seconds)

```bash
# View job details and events
./scripts/test_manual.sh check-job <job_id>

# You should see:
# - Final status: DONE
# - Event history with all events
# - Complete timeline of what happened
```

---

## 🎉 Success!

If you got here, your event-driven system is working perfectly!

---

## What Just Happened?

1. **Manager** received your request and queued it
2. **Downloader** picked it up and processed it
3. **Event Publisher** sent events to RabbitMQ
4. **Consumer** received events and updated Redis
5. **You** tracked the entire workflow!

---

## Next: Run Full Test Suite

Now try the comprehensive tests:

```bash
# Run load test with 5 concurrent jobs
./scripts/test_manual.sh load-test 5

# Check RabbitMQ status
./scripts/test_manual.sh check-rabbitmq

# Check Redis data
./scripts/test_manual.sh check-redis <job_id>

# View live logs
./scripts/test_manual.sh view-logs consumer
```

---

## Troubleshooting

### Services Not Healthy?

```bash
# Check which service is failing
docker-compose ps

# View logs
docker-compose logs [service_name]

# Restart everything
./scripts/test_manual.sh restart
```

### Job Stuck?

```bash
# Check worker logs
docker-compose logs downloader
docker-compose logs translator
docker-compose logs consumer

# Check RabbitMQ queue
open http://localhost:15672
# Login: guest / guest
```

### Need to Start Over?

```bash
# Clean everything
./scripts/test_manual.sh clean

# Start fresh
docker-compose up --build -d
```

---

## Testing Checklist

Quick verification checklist:

- [ ] All services start (health check passes)
- [ ] Job submission works
- [ ] Status updates properly
- [ ] Events recorded in Redis
- [ ] Consumer processes events
- [ ] Job completes successfully

---

## Useful Commands

```bash
# Health check
./scripts/test_manual.sh check-health

# Submit job
./scripts/test_manual.sh submit-job

# Watch job
./scripts/test_manual.sh watch-job <job_id>

# Check job details
./scripts/test_manual.sh check-job <job_id>

# Load test
./scripts/test_manual.sh load-test 10

# View logs
./scripts/test_manual.sh view-logs

# Restart
./scripts/test_manual.sh restart

# Clean up
./scripts/test_manual.sh clean

# Help
./scripts/test_manual.sh help
```

---

## Next Steps

1. ✅ **Read Full Guide**: Check `MANUAL_TESTING_GUIDE.md` for comprehensive testing
2. 🔍 **Explore RabbitMQ**: Open http://localhost:15672 to see event routing
3. 📊 **Check Redis**: Run `./scripts/test_manual.sh check-redis` to see stored data
4. 🧪 **Run Unit Tests**: Try `make test-cov` for automated tests
5. 📚 **Read Architecture**: See `EVENT_DRIVEN_ARCHITECTURE.md` for system design

---

## Key URLs

- **Manager API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **RabbitMQ Management**: http://localhost:15672 (guest/guest)
- **Health Check**: http://localhost:8000/health

---

## Need Help?

1. Check `MANUAL_TESTING_GUIDE.md` for detailed testing scenarios
2. Check `GETTING_STARTED.md` for development workflows
3. Check `EVENT_DRIVEN_ARCHITECTURE.md` for architecture details
4. Run `./scripts/test_manual.sh help` for script commands

Happy Testing! 🚀

