from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field


def _normalise_email(value: object) -> object:
    return value.strip().lower() if isinstance(value, str) else value


Email = Annotated[EmailStr, BeforeValidator(_normalise_email)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str | None


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserOut


class RegisterIn(BaseModel):
    email: Email
    password: str = Field(min_length=10, max_length=256)
    display_name: str | None = Field(default=None, max_length=80)


class LoginIn(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=256)
