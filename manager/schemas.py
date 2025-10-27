"""Manager-specific schemas and models."""

from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from common.schemas import HealthResponse, SubtitleRequest, SubtitleResponse


class SubtitleRequestCreate(SubtitleRequest):
    """Schema for creating a new subtitle request."""

    pass


class SubtitleRequestUpdate(BaseModel):
    """Schema for updating a subtitle request."""

    status: str = Field(..., description="New status")
    error_message: str = Field(None, description="Error message if failed")
    download_url: str = Field(None, description="Download URL if completed")


class SubtitleStatusResponse(BaseModel):
    """Response for subtitle status check."""

    id: UUID = Field(..., description="Request ID")
    status: str = Field(..., description="Current status")
    progress: int = Field(default=0, description="Progress percentage (0-100)")
    message: str = Field(default="", description="Status message")


class QueueStatusResponse(BaseModel):
    """Response for queue status check."""

    download_queue_size: int = Field(
        ..., description="Number of items in download queue"
    )
    translation_queue_size: int = Field(
        ..., description="Number of items in translation queue"
    )
    active_workers: Dict[str, int] = Field(
        ..., description="Number of active workers by type"
    )


class SubtitleTranslateRequest(BaseModel):
    """Request to translate a subtitle file by path."""

    subtitle_path: str = Field(
        ..., description="Path to the subtitle file to translate"
    )
    source_language: str = Field(..., description="Source language code (e.g., 'en')")
    target_language: str = Field(..., description="Target language code (e.g., 'es')")
    video_title: Optional[str] = Field(
        None, description="Optional video title for reference"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "subtitle_path": "/path/to/subtitle.srt",
                "source_language": "en",
                "target_language": "es",
                "video_title": "Sample Video",
            }
        }


class JellyfinWebhookPayload(BaseModel):
    """Payload from Jellyfin webhook for library events."""

    event: str = Field(..., description="Event type (e.g., 'library.item.added')")
    item_type: str = Field(..., description="Item type (e.g., 'Movie', 'Episode')")
    item_name: str = Field(..., description="Name/title of the item")
    item_path: Optional[str] = Field(None, description="File path to the video")
    item_id: Optional[str] = Field(None, description="Jellyfin item ID")
    library_name: Optional[str] = Field(None, description="Library name")
    video_url: Optional[str] = Field(
        None, description="URL to access the video (if available)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "event": "library.item.added",
                "item_type": "Movie",
                "item_name": "Sample Movie",
                "item_path": "/media/movies/sample.mp4",
                "item_id": "abc123",
                "library_name": "Movies",
                "video_url": "http://jellyfin.local/videos/abc123",
            }
        }


class SubtitleDownloadResponse(BaseModel):
    """Response containing subtitle file download information."""

    job_id: UUID = Field(..., description="Job ID")
    filename: str = Field(..., description="Filename of the subtitle file")
    language: str = Field(..., description="Language of the subtitle")
    file_size: Optional[int] = Field(None, description="File size in bytes")


class WebhookAcknowledgement(BaseModel):
    """Acknowledgement response for webhook requests."""

    status: str = Field(default="received", description="Webhook processing status")
    job_id: Optional[UUID] = Field(None, description="Created job ID if applicable")
    message: str = Field(default="", description="Status message")


# Re-export common schemas for convenience
__all__ = [
    "SubtitleRequest",
    "SubtitleResponse",
    "HealthResponse",
    "SubtitleRequestCreate",
    "SubtitleRequestUpdate",
    "SubtitleStatusResponse",
    "QueueStatusResponse",
    "SubtitleTranslateRequest",
    "JellyfinWebhookPayload",
    "SubtitleDownloadResponse",
    "WebhookAcknowledgement",
]
