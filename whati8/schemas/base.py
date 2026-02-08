"""Base schemas with common configurations."""

from pydantic import BaseModel, ConfigDict


class BaseORMModel(BaseModel):
    """Base for schemas mapping to ORM models."""

    model_config = ConfigDict(from_attributes=True)


class BaseRequestModel(BaseModel):
    """Base for API request schemas."""

    model_config = ConfigDict(str_strip_whitespace=True, str_min_length=1)


class BaseResponseModel(BaseModel):
    """Base for API response schemas."""

    model_config = ConfigDict(from_attributes=True)
