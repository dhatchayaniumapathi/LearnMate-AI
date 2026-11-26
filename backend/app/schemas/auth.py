"""Pydantic schemas for authentication and user account lifecycle."""
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    """Payload schema for student account registration."""
    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Student's full display name",
        examples=["Alex Student"],
    )
    email: EmailStr = Field(
        ...,
        description="Unique university or personal email address",
        examples=["alex@university.edu"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Account password (minimum 8 characters)",
        examples=["StrongP@ssw0rd!"],
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Password cannot be empty or contain only whitespace.")
        return v

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if isinstance(v, str):
            trimmed = v.strip()
            if len(trimmed) < 2:
                raise ValueError("Name must contain at least 2 non-whitespace characters.")
            return trimmed
        return v

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class UserLoginRequest(BaseModel):
    """Payload schema for user credential authentication."""
    email: EmailStr = Field(
        ...,
        description="Registered account email address",
        examples=["alex@university.edu"],
    )
    password: str = Field(
        ...,
        min_length=1,
        description="Plaintext password to authenticate",
        examples=["StrongP@ssw0rd!"],
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class UserResponse(BaseModel):
    """Public user profile schema with ORM mode serialization enabled."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Unique user identifier")
    name: str = Field(..., description="Student display name")
    email: str = Field(..., description="Normalized account email")
    is_active: bool = Field(..., description="Account active status")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Last account profile update timestamp")


class TokenResponse(BaseModel):
    """Access token response schema with nested user profile."""
    model_config = ConfigDict(from_attributes=True)

    access_token: str = Field(..., description="Signed JWT access token")
    token_type: str = Field(default="bearer", description="Authentication token type")
    user: UserResponse = Field(..., description="Authenticated user account profile")


class MessageResponse(BaseModel):
    """Generic operation confirmation and status message."""
    message: str = Field(..., description="Status or informational message")
