"""Satu pretrained model dengan lazy loading yang digunakan kembali selama API berjalan."""

import logging
from functools import lru_cache
from threading import Lock

from karhutla.config import Settings, get_settings
from karhutla.errors import AnalysisError
from karhutla.text import token_chunks

logger = logging.getLogger(__name__)


class SentimentEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.pipeline = None
        self.resolved_revision = settings.model_revision
        self.lock = Lock()

    @property
    def loaded(self) -> bool:
        return self.pipeline is not None

    def _load(self):
        if self.pipeline is not None:
            return
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

            options = {
                "revision": self.settings.model_revision,
                "local_files_only": self.settings.local_files_only,
                "trust_remote_code": False,
                "cache_dir": self.settings.model_cache_dir,
            }
            tokenizer = AutoTokenizer.from_pretrained(
                self.settings.model_name,
                use_fast=True,
                **options,
            )
            model = AutoModelForSequenceClassification.from_pretrained(
                self.settings.model_name,
                use_safetensors=True,
                **options,
            )
            self.pipeline = pipeline(
                "text-classification",
                model=model,
                tokenizer=tokenizer,
                device=-1,
            )
            self.resolved_revision = getattr(model.config, "_commit_hash", None) or (
                self.settings.model_revision
            )
        except Exception as exc:
            logger.exception("Could not load the sentiment model")
            raise AnalysisError(
                "The sentiment model could not be loaded. On the first run, internet access "
                "is required to download it. See the server log and README for setup help.",
                status_code=503,
                code="model_unavailable",
            ) from exc

    def analyze(self, text: str) -> list[dict]:
        # Jalankan model loading/inference secara bergantian untuk menghindari download ganda
        # dan lonjakan penggunaan memory.
        with self.lock:
            self._load()
            tokenizer = self.pipeline.tokenizer
            token_limit = min(tokenizer.model_max_length, 512)
            max_tokens = token_limit - tokenizer.num_special_tokens_to_add(pair=False)
            spans = token_chunks(text, tokenizer, max_tokens)
            if len(spans) > self.settings.max_segments:
                raise AnalysisError(
                    f"This input creates more than {self.settings.max_segments} segments. "
                    "Please analyze a shorter excerpt.",
                    code="input_too_large",
                )
            if not spans:
                raise AnalysisError("No analyzable text was found.", code="empty_text")
            try:
                predictions = self.pipeline(
                    [text[start:end] for start, end in spans],
                    batch_size=8,
                    truncation=False,
                )
            except Exception as exc:
                logger.exception("Sentiment inference failed")
                raise AnalysisError(
                    "The model could not analyze this input. Try a shorter excerpt.",
                    status_code=503,
                    code="inference_failed",
                ) from exc
            results = []
            for (start, end), prediction in zip(spans, predictions, strict=True):
                label = prediction["label"].lower()
                # Tampilkan error untuk model yang tidak kompatibel tanpa menebak mapping LABEL_0.
                if label not in {"positive", "neutral", "negative"}:
                    raise AnalysisError(
                        "This model must expose positive, neutral, and negative label names.",
                        status_code=503,
                        code="incompatible_model",
                    )
                results.append(
                    {
                        "char_start": start,
                        "char_end": end,
                        "text": text[start:end],
                        "sentiment": label,
                        "score": float(prediction["score"]),
                    }
                )
            return results


@lru_cache
def get_engine() -> SentimentEngine:
    return SentimentEngine(get_settings())
