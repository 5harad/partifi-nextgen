from pydantic import BaseModel, Field


class PreviewDataResponse(BaseModel):
    partset_id: str
    private_id: str
    title: str | None = None
    composer: str | None = None
    part_names: list[str]
    combined_part_names: list[str]
    part_segments: dict[str, list[int]]
    segment_heights: list[float]
    segment_widths: list[float]
    segment_labels: list[str]
    breaks: dict[str, list[int]]
    spacings: dict[str, float]
    left_margin: int
    segment_urls: dict[str, str]
    images_ready: bool = True
    images_warming: bool = False
    image_progress: float = 100.0


class SaveLayoutRequest(BaseModel):
    breaks: dict[str, list[int]] = Field(default_factory=dict)
    spacings: dict[str, float] = Field(default_factory=dict)


class SaveLayoutResponse(BaseModel):
    status: str = "success"


class CombinePartsRequest(BaseModel):
    action: str
    tag: str


class CombinePartsResponse(BaseModel):
    status: str = "success"


class GeneratePartsResponse(BaseModel):
    status: str = "success"
    job_id: str | None = None


class PartgenProgressResponse(BaseModel):
    error: str | None = None
    status: str | None = None
    progress: float = 0.0
    total_progress: float = 0.0
    is_complete: bool = False


class PartDownloadItem(BaseModel):
    tag: str
    file_name: str
    letter_url: str
    a4_url: str


class PartsDataResponse(BaseModel):
    partset_id: str
    private_id: str | None = None
    public_id: str
    mode: str = "owner"
    title: str | None = None
    composer: str | None = None
    publisher: str | None = None
    score_pdf_url: str | None = None
    parts: list[PartDownloadItem]
    parts_ready: bool
