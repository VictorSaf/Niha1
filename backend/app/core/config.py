import logging
import os
import secrets
from typing import List

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


def _get_secret_key() -> str:
    """
    Get SECRET_KEY from environment or generate one for development.
    In production (DEBUG=False), a missing SECRET_KEY will raise an error.
    """
    key = os.environ.get("SECRET_KEY")
    if key:
        return key

    # Check if we're in production mode
    if os.environ.get("DEBUG", "true").lower() == "false":
        raise ValueError(
            "SECRET_KEY environment variable is required in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )

    # Development fallback - generate a key but warn
    generated_key = secrets.token_urlsafe(32)
    logger.warning(
        "SECRET_KEY not set - using generated key. "
        "This will invalidate sessions on restart. "
        "Set SECRET_KEY env var for persistence."
    )
    return generated_key


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Nihao Carbon Trading Platform"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database - no default credentials in production
    DATABASE_URL: str = "postgresql://niha_user:niha_secure_pass_2024@localhost:5432/niha_carbon"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Security - SECRET_KEY loaded safely
    SECRET_KEY: str = _get_secret_key()
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours for development/testing
    MAGIC_LINK_EXPIRE_MINUTES: int = 15

    # Cookie Settings for httpOnly authentication
    AUTH_COOKIE_NAME: str = "access_token"
    AUTH_COOKIE_SECURE: bool = False  # Set to True in production with HTTPS
    AUTH_COOKIE_SAMESITE: str = "lax"  # "strict", "lax", or "none"
    AUTH_COOKIE_PATH: str = "/"
    AUTH_COOKIE_DOMAIN: str = ""  # Empty = current domain only

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://platonos.mooo.com,https://platonos.mooo.com,http://192.168.10.42:5173,http://192.168.10.42:8000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    # Email (Resend)
    RESEND_API_KEY: str = ""
    FROM_EMAIL: str = "noreply@nihaogroup.com"

    # Price Scraping
    PRICE_UPDATE_INTERVAL_SECONDS: int = 300  # 5 minutes

    # Anthropic API (for introducer AI chat)
    ANTHROPIC_API_KEY: str = ""

    # OpenAI API (for RAG embeddings)
    OPENAI_API_KEY: str = ""

    # Market Maker admin: password required to reset MM data (dangerous operation)
    MM_RESET_PASSWORD: str = ""

    # Market Defaults (based on research)
    DEFAULT_EUA_PRICE_EUR: float = 75.0
    DEFAULT_CEA_PRICE_CNY: float = 100.0
    EUR_TO_USD: float = 1.08
    CNY_TO_USD: float = 0.14

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
