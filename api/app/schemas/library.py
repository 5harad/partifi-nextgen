from pydantic import BaseModel


class LibraryPartItem(BaseModel):
    tag: str
    file_name: str
    letter_url: str
    a4_url: str


class LibraryItem(BaseModel):
    partset_id: str
    private_id: str | None = None
    score_id: str | None = None
    title: str | None = None
    composer: str | None = None
    publisher: str | None = None
    admin: bool
    parts_ready: bool
    parts: list[LibraryPartItem]
    score_pdf_url: str | None = None
    imslp_id: str | None = None


class LibraryResponse(BaseModel):
    items: list[LibraryItem]


class FavoriteStatusResponse(BaseModel):
    favorite: bool


class FavoriteActionRequest(BaseModel):
    action: str
