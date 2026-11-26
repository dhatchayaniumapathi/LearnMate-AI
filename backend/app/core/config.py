"""Application configuration module."""
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "LearnMate AI API"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: Union[bool, str] = True
    API_V1_STR: str = "/api/v1"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v: Union[bool, str]) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on", "debug")
        return bool(v)

    # Database (Neon PostgreSQL connection string)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/learnmate"
    DIRECT_DATABASE_URL: Union[str, None] = None
    TEST_DATABASE_URL: Union[str, None] = None
    DATABASE_ECHO: bool = False

    # Security & Tokens
    SECRET_KEY: str = "development-secret-key-replace-in-production-min-32-bytes"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "learnmate-ai"
    JWT_AUDIENCE: str = "learnmate-ai-users"

    # CORS
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v  # type: ignore
        raise ValueError(v)

    # ChromaDB
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_data"

    # LLM Providers (optional)
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
