"""Shared Pydantic schemas for the subtitle management system."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from common.utils import DateTimeUtils


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
    JOB_FAILED = "job.failed"


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
        default_factory=uuid4, description="Unique identifier for the request"
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
    """Task for downloading subtitles."""

    request_id: UUID = Field(..., description="ID of the original request")
    video_url: str = Field(..., description="URL of the video file")
    video_title: str = Field(..., description="Title of the video")
    language: str = Field(..., description="Source language code")
    preferred_sources: List[str] = Field(
        default_factory=list, description="Preferred subtitle sources"
    )


class TranslationTask(BaseModel):
    """Task for translating subtitles."""

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
