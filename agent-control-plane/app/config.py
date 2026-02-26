import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_timeout_seconds: int = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "45"))
    fallback_timeout_seconds: int = int(os.getenv("FALLBACK_TIMEOUT_SECONDS", "45"))
    fallback_confidence_threshold: float = float(os.getenv("FALLBACK_CONFIDENCE_THRESHOLD", "0.7"))


settings = Settings()
