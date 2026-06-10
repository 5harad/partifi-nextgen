from pydantic import BaseModel


class ImslpInfoResponse(BaseModel):
    imslp_id: str
    title: str
    composer: str
    publisher: str
    copyright_raw: str
    file_type: str


class CreateFromImslpRequest(BaseModel):
    imslp_id: str
    title: str
    composer: str
    publisher: str = ""
    copyright: str = "unknown"
