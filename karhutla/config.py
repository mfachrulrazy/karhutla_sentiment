"""Modul konfigurasi sederhana; nilai default dapat digunakan tanpa file .env."""

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    youtube_api_key: str = field(default="", repr=False)
    model_name: str = "w11wo/indonesian-roberta-base-sentiment-classifier"
    model_revision: str = "ac452dcb0f4966130bba44f4ee0013bb5d52c282"
    local_files_only: bool = False
    max_text_characters: int = 30_000
    max_segments: int = 300
    model_cache_dir: str = str(Path(__file__).resolve().parents[1] / ".cache" / "models")


@lru_cache
def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        youtube_api_key=os.getenv("YOUTUBE_API_KEY", "").strip(),
        model_name=os.getenv("SENTIMENT_MODEL", Settings.model_name),
        model_revision=os.getenv("SENTIMENT_MODEL_REVISION", Settings.model_revision),
        local_files_only=os.getenv("MODEL_LOCAL_FILES_ONLY", "false").lower() == "true",
        max_text_characters=int(os.getenv("MAX_TEXT_CHARACTERS", "30000")),
        max_segments=int(os.getenv("MAX_SEGMENTS", "300")),
        model_cache_dir=os.getenv("MODEL_CACHE_DIR", Settings.model_cache_dir),
    )
