"""Kontrak request dan response yang digunakan bersama oleh API dan dashboard."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Sentiment = Literal["positive", "neutral", "negative"]


class AnalyzeRequest(BaseModel):
    youtube_mode: Literal["transcript", "comments"] = "transcript"
    max_comments: int = Field(default=100, ge=1, le=100)
    text: str | None = Field(default=None, max_length=100_000)
    url: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def exactly_one_input(self):
        self.text = self.text.strip() if self.text else None
        self.url = self.url.strip() if self.url else None
        if bool(self.text) == bool(self.url):
            raise ValueError("Provide exactly one non-empty field: text or url.")
        if self.youtube_mode == "comments" and not self.url:
            raise ValueError("Comments mode requires a YouTube video URL.")
        return self


class SourceInfo(BaseModel):
    kind: Literal["text", "news", "youtube"]
    url: str | None = None
    title: str | None = None
    language: str = "id"
    transcript_generated: bool | None = None
    youtube_mode: Literal["transcript", "comments"] | None = None
    comment_order: str | None = None
    comments_fetched: int | None = None


class SegmentResult(BaseModel):
    comment_id: str | None = None
    id: int
    text: str
    sentiment: Sentiment
    score: float = Field(ge=0, le=1)
    char_start: int
    char_end: int
    start_seconds: float | None = None
    end_seconds: float | None = None


class SentimentSummary(BaseModel):
    unit: Literal["segments", "comments"] = "segments"
    total_units: int | None = None
    total_segments: int
    counts: dict[Sentiment, int]
    percentages: dict[Sentiment, float]


class TermCount(BaseModel):
    term: str
    count: int


class CommentResult(BaseModel):
    comment_id: str
    text: str
    sentiment: Sentiment
    score: float
    like_count: int
    published_at: str
    segment_count: int


class AnalysisResult(BaseModel):
    comments: list[CommentResult] = Field(default_factory=list)
    source: SourceInfo
    analyzed_at: datetime
    model: str
    model_revision: str
    character_count: int
    summary: SentimentSummary
    segments: list[SegmentResult]
    keywords: list[TermCount]
    word_frequencies: dict[str, int]
    warnings: list[str]
