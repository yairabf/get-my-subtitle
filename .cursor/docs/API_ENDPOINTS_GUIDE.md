# API Endpoints Guide

This guide explains the different API endpoints and when to use each one.

## Endpoint Categories

### 1. Job Status Endpoints

There are **two different endpoints** for checking job status, each serving a different purpose:

#### `GET /subtitles/status/{job_id}` - Lightweight Status Check

**Use this when:**
- Polling for job progress
- Building progress bars in UI
- Quick status checks
- You only need to know if the job is done

**Returns:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "processing",
  "progress": 50,
  "message": "Status: processing"
}
```

**Response includes:**
- Job ID
- Status (as string)
- Progress percentage (0-100)
- Status message

**Why use this?**
- ✅ Lightweight response
- ✅ Calculated progress percentage
- ✅ Perfect for polling
- ✅ Minimal data transfer

---

#### `GET /subtitles/{job_id}` - Full Job Details

**Use this when:**
- You need complete job information
- Displaying detailed job information in UI
- Debugging or troubleshooting
- You need video URL, title, timestamps, etc.

---

#### `GET /subtitles/{job_id}/events` - Job Event History

**Use this when:**
- Debugging workflow issues
- Auditing job processing timeline
- Tracking which services processed the job
- Investigating failures or unexpected behavior

**Returns:**
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "event_count": 3,
  "events": [
    {
      "event_type": "subtitle.translated",
      "timestamp": "2024-01-01T00:05:00Z",
      "source": "translator",
      "payload": {
        "translated_path": "/subtitles/translated.srt",
        "download_url": "https://example.com/subtitle.srt"
      }
    },
    {
      "event_type": "subtitle.download.requested",
      "timestamp": "2024-01-01T00:00:00Z",
      "source": "manager",
      "payload": {
        "video_url": "https://example.com/video.mp4",
        "language": "en"
      }
    }
  ]
}
```

**Response includes:**
- Complete event timeline (most recent first)
- Event types and timestamps
- Source service for each event
- Event payloads with contextual data

**Why use this?**
- ✅ Complete audit trail
- ✅ Workflow visibility
- ✅ Debugging failures
- ✅ Performance analysis

**Returns:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "video_url": "https://example.com/video.mp4",
  "video_title": "Sample Video",
  "language": "en",
  "target_language": "es",
  "status": "processing",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:05:00Z",
  "error_message": null,
  "download_url": null
}
```

**Response includes:**
- Everything from lightweight status PLUS:
- Video URL
- Video title
- Source and target languages
- Created/updated timestamps
- Error messages (if any)
- Download URL (if available)

**Why use this?**
- ✅ Complete job information
- ✅ Video metadata
- ✅ Timestamps for audit trails
- ✅ Error details for debugging

---

## Quick Reference

| Endpoint | Purpose | Response Size | Use Case |
|----------|---------|---------------|----------|
| `GET /subtitles/status/{job_id}` | Quick status | Small | Polling, progress bars |
| `GET /subtitles/{job_id}` | Full details | Large | Details page, debugging |

## Example Usage Patterns

### Pattern 1: Progress Tracking
```javascript
// Poll for status updates
async function trackProgress(jobId) {
  const response = await fetch(`/subtitles/status/${jobId}`);
  const { status, progress } = await response.json();
  
  updateProgressBar(progress);
  
  if (status !== 'completed' && status !== 'failed') {
    setTimeout(() => trackProgress(jobId), 2000);
  }
}
```

### Pattern 2: Job Details Display
```javascript
// Get full job information for details page
async function showJobDetails(jobId) {
  const response = await fetch(`/subtitles/${jobId}`);
  const job = await response.json();
  
  displayJobInfo({
    title: job.video_title,
    url: job.video_url,
    status: job.status,
    created: job.created_at,
    error: job.error_message
  });
}
```

### Pattern 3: Combined Approach
```javascript
// Poll with lightweight endpoint, get details when done
async function processJob(jobId) {
  // Step 1: Poll for completion
  let status;
  do {
    const response = await fetch(`/subtitles/status/${jobId}`);
    const data = await response.json();
    status = data.status;
    updateProgress(data.progress);
    await sleep(2000);
  } while (status === 'pending' || status === 'processing');
  
  // Step 2: Get full details when complete
  const detailsResponse = await fetch(`/subtitles/${jobId}`);
  const fullJob = await detailsResponse.json();
  
  if (status === 'completed') {
    showSuccess(fullJob);
  } else {
    showError(fullJob.error_message);
  }
}
```

## Best Practices

1. **For Progress Updates**: Use `/subtitles/status/{job_id}`
   - Lower bandwidth
   - Faster response times
   - Built-in progress calculation

2. **For Final Results**: Use `/subtitles/{job_id}`
   - Get complete information
   - Access download URLs
   - See detailed error messages

3. **Avoid Over-Polling**: 
   - Poll every 2-5 seconds (not faster)
   - Consider using webhooks for production
   - Stop polling after completion/failure

4. **Error Handling**:
   - Both endpoints return 404 if job doesn't exist
   - Check for error_message in full details when status is 'failed'
   - Use status messages for user-friendly feedback

