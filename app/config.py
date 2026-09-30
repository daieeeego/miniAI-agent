import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    jev_mode: str = "mock"
    high_confidence: float = 0.85
    low_confidence: float = 0.55
    jev_model: str = "jev-latest"
    openai_model: str = ""
    typesafe_secret_version: str = ""
    openai_secret_version: str = ""
    timeout_seconds: float = 20.0

    def __post_init__(self):
        if self.jev_mode not in {"mock", "live"}:
            raise ValueError("JEV_MODE must be mock or live")
        if not 0 <= self.low_confidence < self.high_confidence <= 1:
            raise ValueError("thresholds must satisfy 0 <= low < high <= 1")
        if not 0 < self.timeout_seconds <= 120:
            raise ValueError("API_TIMEOUT_SECONDS must be in (0, 120]")

    @classmethod
    def from_env(cls):
        return cls(
            jev_mode=os.getenv("JEV_MODE", "mock"),
            high_confidence=float(os.getenv("JEV_HIGH_CONFIDENCE", "0.85")),
            low_confidence=float(os.getenv("JEV_LOW_CONFIDENCE", "0.55")),
            jev_model=os.getenv("JEV_MODEL", "jev-latest"),
            openai_model=os.getenv("OPENAI_MODEL", ""),
            typesafe_secret_version=os.getenv("TYPESAFE_SECRET_VERSION", ""),
            openai_secret_version=os.getenv("OPENAI_SECRET_VERSION", ""),
            timeout_seconds=float(os.getenv("API_TIMEOUT_SECONDS", "20")),
        )
