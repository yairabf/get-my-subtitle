"""Shared Pydantic schemas for the subtitle management system."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from common.utils import DateTimeUtils, JobIdUtils


class SubtitleStatus(str, Enum):
    """Status of subtitle processing."""

    PENDING = "pending"
    DOWNLOAD_QUEUED = "download_queued"
    DOWNLOAD_IN_PROGRESS = "download_in_progress"
    TRANSLATE_QUEUED = "translate_queued"
    TRANSLATE_IN_PROGRESS = "translate_in_progress"
    DONE = "done"
    FAILED = "failed"
    SUBTITLE_MISSING = "subtitle_missing"
    # Legacy statuses for backward compatibility
    DOWNLOADING = "downloading"
    TRANSLATING = "translating"
    COMPLETED = "completed"


class EventType(str, Enum):
    """Types of events in the subtitle processing workflow."""

    SUBTITLE_DOWNLOAD_REQUESTED = "subtitle.download.requested"
    SUBTITLE_READY = "subtitle.ready"
    SUBTITLE_MISSING = "subtitle.missing"
    SUBTITLE_TRANSLATE_REQUESTED = "subtitle.translate.requested"
    SUBTITLE_TRANSLATED = "subtitle.translated"
    TRANSLATION_COMPLETED = "translation.completed"
    JOB_FAILED = "job.failed"
    MEDIA_FILE_DETECTED = "media.file.detected"
    SUBTITLE_REQUESTED = "subtitle.requested"


class SubtitleRequest(BaseModel):
    """Request to process subtitles for a video."""

    video_url: str = Field(..., description="URL of the video file")
    video_title: str = Field(..., description="Title of the video")
    language: str = Field(..., description="Source language code (e.g., 'en')")
    target_language: Optional[str] = Field(
        None, description="Target language code (e.g., 'es')"
    )
    preferred_sources: List[str] = Field(
        default_factory=list, description="Preferred subtitle sources"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "video_url": "https://example.com/video.mp4",
                "video_title": "Sample Video",
                "language": "en",
                "target_language": "es",
                "preferred_sources": ["opensubtitles"],
            }
        }


class SubtitleResponse(BaseModel):
    """Response containing subtitle processing information."""

    id: UUID = Field(
        default_factory=JobIdUtils.generate_job_id,
        description="Unique identifier for the request",
    )
    video_url: str = Field(..., description="URL of the video file")
    video_title: str = Field(..., description="Title of the video")
    language: str = Field(..., description="Source language code")
    target_language: Optional[str] = Field(None, description="Target language code")
    status: SubtitleStatus = Field(
        default=SubtitleStatus.PENDING, description="Current processing status"
    )
    created_at: datetime = Field(
        default_factory=DateTimeUtils.get_current_utc_datetime,
        description="When the request was created",
    )
    updated_at: datetime = Field(
        default_factory=DateTimeUtils.get_current_utc_datetime,
        description="When the request was last updated",
    )
    error_message: Optional[str] = Field(
        None, description="Error message if processing failed"
    )
    download_url: Optional[str] = Field(
        None, description="URL to download processed subtitles"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "video_url": "https://example.com/video.mp4",
                "video_title": "Sample Video",
                "language": "en",
                "target_language": "es",
                "status": "pending",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "error_message": None,
                "download_url": None,
            }
        }


class DownloadTask(BaseModel):
    """
    Internal task model for downloading subtitles.

    This model is used for internal worker queue messages.
    For API-level requests, use SubtitleDownloadRequest instead.
    """

    request_id: UUID = Field(..., description="ID of the original request")
    video_url: str = Field(..., description="URL of the video file")
    video_title: str = Field(..., description="Title of the video")
    language: str = Field(..., description="Source language code")
    preferred_sources: List[str] = Field(
        default_factory=list, description="Preferred subtitle sources"
    )


class TranslationTask(BaseModel):
    """
    Internal task model for translating subtitles.

    This model is used for internal worker queue messages.
    For API-level requests, use TranslationRequest instead.
    """

    request_id: UUID = Field(..., description="ID of the original request")
    subtitle_file_path: str = Field(
        ..., description="Path to the downloaded subtitle file"
    )
    source_language: str = Field(..., description="Source language code")
    target_language: str = Field(..., description="Target language code")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(default="healthy", description="Service health status")
    timestamp: datetime = Field(
        default_factory=DateTimeUtils.get_current_utc_datetime,
        description="Current timestamp",
    )
    version: str = Field(default="1.0.0", description="Service version")


class SubtitleEvent(BaseModel):
    """Event for subtitle processing workflow."""

    event_type: EventType = Field(..., description="Type of event")
    job_id: UUID = Field(..., description="Job identifier")
    timestamp: datetime = Field(
        default_factory=DateTimeUtils.get_current_utc_datetime,
        description="When the event occurred",
    )
    source: str = Field(
        ..., description="Source service (manager, downloader, translator, consumer)"
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict, description="Event payload data"
    )
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "event_type": "subtitle.ready",
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "timestamp": "2024-01-01T00:00:00Z",
                "source": "downloader",
                "payload": {
                    "subtitle_path": "/path/to/subtitle.srt",
                    "language": "en",
                    "download_url": "https://example.com/subtitles/123.srt",
                },
                "metadata": None,
            }
        }


class TranslationCheckpoint(BaseModel):
    """Checkpoint data for resuming translation after interruption."""

    request_id: UUID = Field(
        ..., description="Unique identifier for the translation request"
    )
    subtitle_file_path: str = Field(..., description="Path to the source subtitle file")
    source_language: str = Field(..., description="Source language code")
    target_language: str = Field(..., description="Target language code")
    total_chunks: int = Field(..., description="Total number of chunks to translate")
    completed_chunks: List[int] = Field(
        default_factory=list, description="List of completed chunk indices (0-based)"
    )
    translated_segments: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of translated SubtitleSegment objects as dictionaries",
    )
    checkpoint_path: str = Field(..., description="Path to the checkpoint file")
    created_at: datetime = Field(
        default_factory=DateTimeUtils.get_current_utc_datetime,
        description="When the checkpoint was created",
    )
    updated_at: datetime = Field(
        default_factory=DateTimeUtils.get_current_utc_datetime,
        description="When the checkpoint was last updated",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "123e4567-e89b-12d3-a456-426614174000",
                "subtitle_file_path": "/path/to/subtitle.srt",
                "source_language": "en",
                "target_language": "es",
                "total_chunks": 10,
                "completed_chunks": [0, 1, 2, 3],
                "translated_segments": [
                    {
                        "index": 1,
                        "start_time": "00:00:01,000",
                        "end_time": "00:00:04,000",
                        "text": "Hola mundo",
                    }
                ],
                "checkpoint_path": "/path/to/checkpoint.json",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:05:00Z",
            }
        }


# ============================================================================
# Event Envelope and API Request Models
# ============================================================================


class EventEnvelope(BaseModel):
    """
    Standardized envelope for wrapping events published to event exchange.

    Provides consistent metadata structure for observability and traceability
    across services. Only wraps events (not work queue tasks).
    """

    event_id: UUID = Field(
        default_factory=JobIdUtils.generate_job_id,
        description="Unique event identifier",
    )
    event_type: EventType = Field(..., description="Type of event")
    source: str = Field(
        ...,
        description="Service that published the event (manager, downloader, translator, scanner)",
    )
    timestamp: datetime = Field(
        default_factory=DateTimeUtils.get_current_utc_datetime,
        description="When the event occurred",
    )
    payload: Dict[str, Any] = Field(..., description="Event-specific data")
    correlation_id: Optional[UUID] = Field(
        None,
        description="Request tracing identifier for correlating events across services",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional context (version, environment, etc.)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "123e4567-e89b-12d3-a456-426614174000",
                "event_type": "subtitle.ready",
                "source": "downloader",
                "timestamp": "2024-01-01T00:00:00Z",
                "payload": {
                    "job_id": "123e4567-e89b-12d3-a456-426614174000",
                    "subtitle_path": "/path/to/subtitle.srt",
                    "language": "en",
                },
                "correlation_id": "987e6543-e21b-43d2-b654-321987654321",
                "metadata": {"version": "1.0.0", "environment": "production"},
            }
        }


class SubtitleDownloadRequest(BaseModel):
    """
    API-level request model for subtitle download operations.

    This model validates external user inputs for subtitle download requests.
    The manager service converts this to DownloadTask before queueing.
    """

    video_url: HttpUrl = Field(
        ..., description="URL of the video file (must be valid HTTP/HTTPS URL)"
    )
    video_title: str = Field(
        ..., min_length=1, max_length=500, description="Title of the video"
    )
    language: str = Field(
        ...,
        pattern=r"^[a-z]{2}$",
        description="Source language code (ISO 639-1, e.g., 'en', 'es')",
    )
    target_language: Optional[str] = Field(
        None,
        pattern=r"^[a-z]{2}$",
        description="Target language code for translation (ISO 639-1, e.g., 'es', 'fr')",
    )
    preferred_sources: List[str] = Field(
        default_factory=list, description="Preferred subtitle sources"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "video_url": "https://example.com/video.mp4",
                "video_title": "Sample Video",
                "language": "en",
                "target_language": "es",
                "preferred_sources": ["opensubtitles"],
            }
        }


class TranslationRequest(BaseModel):
    """
    API-level request model for subtitle translation operations.

    This model validates external user inputs for translation requests.
    The manager service converts this to TranslationTask before queueing.
    """

    subtitle_file_path: str = Field(
        ..., min_length=1, description="Path to the subtitle file to translate"
    )
    source_language: str = Field(
        ...,
        pattern=r"^[a-z]{2}$",
        description="Source language code (ISO 639-1, e.g., 'en', 'es')",
    )
    target_language: str = Field(
        ...,
        pattern=r"^[a-z]{2}$",
        description="Target language code (ISO 639-1, e.g., 'es', 'fr')",
    )
    video_title: Optional[str] = Field(
        None, description="Optional video title for context"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "subtitle_file_path": "/path/to/subtitle.srt",
                "source_language": "en",
                "target_language": "es",
                "video_title": "Sample Video",
            }
        }


class JobRecord(BaseModel):
    """
    Standardized job metadata model for API responses and monitoring.

    Provides a normalized view of job status and metadata without exposing
    all internal Redis data structures. Can be extended for audit/history tracking.
    """

    job_id: UUID = Field(..., description="Unique job identifier")
    status: SubtitleStatus = Field(..., description="Current processing status")
    created_at: datetime = Field(..., description="Job creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    task_type: Literal["download", "translation", "download_with_translation"] = Field(
        ..., description="Type of task being processed"
    )
    video_url: Optional[str] = Field(None, description="Source video URL")
    video_title: Optional[str] = Field(None, description="Video title")
    language: Optional[str] = Field(None, description="Source language code")
    target_language: Optional[str] = Field(
        None, description="Target language code (if translation)"
    )
    result_url: Optional[str] = Field(
        None, description="URL to download completed subtitle"
    )
    error_message: Optional[str] = Field(
        None, description="Error details if status is FAILED"
    )
    progress_percentage: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Calculated progress percentage (0-100)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "download_in_progress",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:05:00Z",
                "task_type": "download_with_translation",
                "video_url": "https://example.com/video.mp4",
                "video_title": "Sample Video",
                "language": "en",
                "target_language": "es",
                "result_url": None,
                "error_message": None,
                "progress_percentage": 45,
            }
        }


# ============================================================================
# Event Factory Functions
# ============================================================================


def create_subtitle_ready_event(
    job_id: UUID,
    subtitle_path: str,
    language: str,
    source: str = "downloader",
    download_url: Optional[str] = None,
) -> SubtitleEvent:
    """
    Factory function for creating SubtitleEvent with SUBTITLE_READY type.

    Provides type-safe convenience method for creating subtitle ready events
    with consistent payload structure.

    Args:
        job_id: Unique job identifier
        subtitle_path: Path to the downloaded subtitle file
        language: Language code of the subtitle
        source: Service that published the event (default: "downloader")
        download_url: Optional URL to download the subtitle file

    Returns:
        SubtitleEvent with event_type set to SUBTITLE_READY

    Example:
        >>> from common.utils import JobIdUtils
        >>> event = create_subtitle_ready_event(
        ...     job_id=JobIdUtils.generate_job_id(),
        ...     subtitle_path="/storage/subtitles/123.srt",
        ...     language="en",
        ...     download_url="https://example.com/subtitles/123.srt"
        ... )
        >>> event.event_type == EventType.SUBTITLE_READY
        True
    """
    payload: Dict[str, Any] = {
        "subtitle_path": subtitle_path,
        "language": language,
    }
    if download_url:
        payload["download_url"] = download_url

    return SubtitleEvent(
        event_type=EventType.SUBTITLE_READY,
        job_id=job_id,
        source=source,
        payload=payload,
    )
