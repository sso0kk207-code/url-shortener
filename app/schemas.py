from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator

RESERVED = {"docs", "redoc", "openapi.json", "auth", "links", "health"}


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LinkCreate(BaseModel):
    url: HttpUrl
    custom_code: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{3,32}$", examples=["my-promo"])
    expires_at: datetime | None = None

    @field_validator("custom_code")
    @classmethod
    def not_reserved(cls, v: str | None) -> str | None:
        if v and v.lower() in RESERVED:
            raise ValueError("this code is reserved")
        return v


class LinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    url: str
    short_url: str | None = None
    created_at: datetime
    expires_at: datetime | None
    clicks_total: int


class DayStat(BaseModel):
    day: str
    clicks: int


class RefererStat(BaseModel):
    referer: str
    clicks: int


class LinkStats(BaseModel):
    code: str
    clicks_total: int
    unique_visitors: int
    by_day: list[DayStat]
    top_referers: list[RefererStat]
