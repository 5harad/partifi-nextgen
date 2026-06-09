from pydantic import BaseModel


class SearchResultItem(BaseModel):
    public_id: str
    score_id: str
    imslp_id: str | None = None
    title: str | None = None
    composer: str | None = None
    publisher: str | None = None
    score_pdf_url: str


class SearchResponse(BaseModel):
    results: list[SearchResultItem]


class CreateFromScoreRequest(BaseModel):
    score_id: str
    title: str
    composer: str
    publisher: str = ""
    copyright: str = "before 1923"
