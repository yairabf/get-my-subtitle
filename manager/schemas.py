"""Manager-specific schemas and models."""

from typing import Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field

from common.schemas import SubtitleRequest, SubtitleResponse, HealthResponse


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


# Re-export common schemas for convenience
__all__ = [
    "SubtitleRequest",
    "SubtitleResponse",
    "HealthResponse",
    "SubtitleRequestCreate",
    "SubtitleRequestUpdate",
    "SubtitleStatusResponse",
    "QueueStatusResponse",
]
