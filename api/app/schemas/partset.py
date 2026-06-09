from pydantic import BaseModel


class PartsetCreateResponse(BaseModel):
    status: str
    id: str
    action: str | None = None


class ImportProgressResponse(BaseModel):
    error: str | None = None
    status: str | None = None
    progress: float = 0.0
    total_progress: float = 0.0
    is_complete: bool = False
