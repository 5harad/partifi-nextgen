from typing import Literal

from pydantic import BaseModel, Field


class OrientationOption(BaseModel):
    degrees: int
    orientation: Literal["portrait", "landscape"]
    preview_url: str


class OrientationDataResponse(BaseModel):
    private_id: str
    score_orientation: Literal["portrait", "landscape"]
    current_rotation_degrees: int = 0
    current_orientation: Literal["portrait", "landscape"]
    rotation_options: list[OrientationOption]
    reimport_in_progress: bool = False
    reimport_progress: float = 0.0
    reimport_error: str | None = None
    reimport_error_message: str | None = None


class ReorientRequest(BaseModel):
    rotation_degrees: int = Field(ge=0, le=270)


class ReorientResponse(BaseModel):
    status: str
    job_id: str


class RetryPageCacheResponse(BaseModel):
    status: str = "started"
