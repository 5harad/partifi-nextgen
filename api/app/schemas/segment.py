from pydantic import BaseModel, Field


class SegmentItem(BaseModel):
    pos: list[float]
    tags: str = ""
    tag_is_suggestion: bool = False
    label: str = ""
    label_is_suggestion: bool = False


class PageSegmentData(BaseModel):
    left_margin: float = 0.0
    right_margin: float = 100.0
    rotation: float = 0.0
    segments: list[SegmentItem] = Field(default_factory=list)


class SegmentDataResponse(BaseModel):
    score_id: str
    partset_id: str
    private_id: str
    num_pages: int
    pages: dict[str, PageSegmentData]
    image_urls: dict[str, dict[str, str]]
    images_ready: bool = True
    images_warming: bool = False
    image_progress: float = 100.0


class SavePageSegmentsRequest(BaseModel):
    left_margin: float
    right_margin: float
    rotation: float
    segments: list[SegmentItem]


class SaveAllPageSegmentsRequest(BaseModel):
    pages: dict[str, PageSegmentData]


class SavePageSegmentsResponse(BaseModel):
    status: str
