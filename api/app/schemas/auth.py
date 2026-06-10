from pydantic import BaseModel


class UserResponse(BaseModel):
    id: str
    name: str | None = None


class AuthMeResponse(BaseModel):
    user: UserResponse | None = None


class GoogleLoginRequest(BaseModel):
    access_token: str | None = None
    id_token: str | None = None


class DevLoginRequest(BaseModel):
    user_id: str = "dev-user"
    name: str = "Dev User"
