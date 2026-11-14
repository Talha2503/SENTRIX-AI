from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "SENTRIX AI"
    DATABASE_URL: str = "postgresql+psycopg2://sentrix:sentrix@localhost:5432/sentrix"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    UPLOAD_DIR: str = "uploads"
    CORS_ORIGINS: str = "http://localhost:3000"
    # True on serverless hosts such as Vercel: run the investigation inside the request,
    # because the process is frozen once the response has been sent.
    INLINE_INVESTIGATION: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("DATABASE_URL")
    @classmethod
    def use_psycopg2_driver(cls, value: str) -> str:
        """Hosted providers hand out postgres:// or postgresql:// URLs; SQLAlchemy needs the driver name."""
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg2://" + value[len(prefix):]
        return value


settings = Settings()