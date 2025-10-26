"""Shared Pydantic schemas for the subtitle management system."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class SubtitleStatus(str, Enum):
    """Status of subtitle processing."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSLATING = "translating"
    COMPLETED = "completed"
    FAILED = "failed"


class SubtitleRequest(BaseModel):
    """Request to process subtitles for a video."""
    video_url: str = Field(..., description="URL of the video file")
    video_title: str = Field(..., description="Title of the video")
    language: str = Field(..., description="Source language code (e.g., 'en')")
    target_language: Optional[str] = Field(None, description="Target language code (e.g., 'es')")
    preferred_sources: List[str] = Field(default_factory=list, description="Preferred subtitle sources")
    
    class Config:
        json_schema_extra = {
            "example": {
                "video_url": "https://example.com/video.mp4",
                "video_title": "Sample Video",
                "language": "en",
                "target_language": "es",
                "preferred_sources": ["opensubtitles"]
            }
        }


class SubtitleResponse(BaseModel):
    """Response containing subtitle processing information."""
    id: UUID = Field(default_factory=uuid4, description="Unique identifier for the request")
    video_url: str = Field(..., description="URL of the video file")
    video_title: str = Field(..., description="Title of the video")
    language: str = Field(..., description="Source language code")
    target_language: Optional[str] = Field(None, description="Target language code")
    status: SubtitleStatus = Field(default=SubtitleStatus.PENDING, description="Current processing status")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When the request was created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="When the request was last updated")
    error_message: Optional[str] = Field(None, description="Error message if processing failed")
    download_url: Optional[str] = Field(None, description="URL to download processed subtitles")
    
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
                "download_url": None
            }
        }


class DownloadTask(BaseModel):
    """Task for downloading subtitles."""
    request_id: UUID = Field(..., description="ID of the original request")
    video_url: str = Field(..., description="URL of the video file")
    video_title: str = Field(..., description="Title of the video")
    language: str = Field(..., description="Source language code")
    preferred_sources: List[str] = Field(default_factory=list, description="Preferred subtitle sources")


class TranslationTask(BaseModel):
    """Task for translating subtitles."""
    request_id: UUID = Field(..., description="ID of the original request")
    subtitle_file_path: str = Field(..., description="Path to the downloaded subtitle file")
    source_language: str = Field(..., description="Source language code")
    target_language: str = Field(..., description="Target language code")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(default="healthy", description="Service health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Current timestamp")
    version: str = Field(default="1.0.0", description="Service version")
