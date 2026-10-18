"""Hubungkan extraction, prediksi model, dan statistik deskriptif sederhana."""

from collections import Counter
from datetime import datetime, timezone

from karhutla.config import Settings
from karhutla.errors import AnalysisError
from karhutla.extraction import ExtractedContent, extract_url
from karhutla.schemas import (
    AnalysisResult,
    AnalyzeRequest,
    CommentResult,
    SegmentResult,
    SentimentSummary,
    SourceInfo,
    TermCount,
)
from karhutla.text import clean_text, word_statistics


def analyze_request(request: AnalyzeRequest, engine, settings: Settings) -> AnalysisResult:
    if request.youtube_mode == "comments":
        return analyze_comments(request, engine, settings)
    content = (
        extract_url(request.url)
        if request.url
        else ExtractedContent(text=request.text, source=SourceInfo(kind="text"))
    )
    text = clean_text(content.text)
    if not text or not any(character.isalpha() for character in text):
        raise AnalysisError("Enter text containing words to analyze.", code="empty_text")
    if len(text) > settings.max_text_characters:
        raise AnalysisError(
            f"Please use at most {settings.max_text_characters:,} characters. "
            "For a longer article or video, paste an excerpt.",
            code="input_too_large",
        )

    predictions = engine.analyze(text)
    segments = []
    for index, prediction in enumerate(predictions, start=1):
        segment = SegmentResult(id=index, **prediction)
        overlapping = [
            cue
            for cue in content.cues
            if cue.char_start < segment.char_end and cue.char_end > segment.char_start
        ]
        if overlapping:
            segment.start_seconds = overlapping[0].start_seconds
            segment.end_seconds = overlapping[-1].end_seconds
        segments.append(segment)

    counts = {label: 0 for label in ("positive", "neutral", "negative")}
    for segment in segments:
        counts[segment.sentiment] += 1
    frequencies, keywords = word_statistics(text)
    warnings = [
        *content.warnings,
        "Predictions describe text tone; a harmful event is not necessarily an expressed opinion.",
        "Model scores are not calibrated probabilities of correctness.",
        "Percentages count analyzed text segments, not people or population opinion.",
    ]
    return AnalysisResult(
        source=content.source,
        analyzed_at=datetime.now(timezone.utc),
        model=settings.model_name,
        model_revision=getattr(engine, "resolved_revision", settings.model_revision),
        character_count=len(text),
        summary=SentimentSummary(
            total_units=len(segments),
            total_segments=len(segments),
            counts=counts,
            percentages={
                label: round(count / len(segments) * 100, 2) for label, count in counts.items()
            },
        ),
        segments=segments,
        keywords=[TermCount(term=term, count=count) for term, count in keywords],
        word_frequencies=frequencies,
        warnings=warnings,
    )


def analyze_comments(request: AnalyzeRequest, engine, settings: Settings) -> AnalysisResult:
    from karhutla.comments import fetch_comments

    video_id, fetched = fetch_comments(request.url, settings.youtube_api_key, request.max_comments)
    comments, segments, texts = [], [], []
    offset = 0
    skipped = 0
    for comment in fetched:
        text = comment["text"]
        if not any(c.isalpha() for c in text) or offset + len(text) > settings.max_text_characters:
            skipped += 1
            continue
        result = analyze_request(AnalyzeRequest(text=text), engine, settings)
        if len(segments) + len(result.segments) > settings.max_segments:
            skipped += 1
            continue
        counts = Counter(segment.sentiment for segment in result.segments)
        # Gunakan label mayoritas segment; jika seri, gunakan jumlah score model.
        label = max(
            counts,
            key=lambda name: (
                counts[name],
                sum(s.score for s in result.segments if s.sentiment == name),
            ),
        )
        matching = [s.score for s in result.segments if s.sentiment == label]
        comments.append(
            CommentResult(
                **comment,
                sentiment=label,
                score=sum(matching) / len(matching),
                segment_count=len(result.segments),
            )
        )
        for segment in result.segments:
            segment.id = len(segments) + 1
            segment.comment_id = comment["comment_id"]
            segment.char_start += offset
            segment.char_end += offset
            segments.append(segment)
        texts.append(text)
        offset += len(text) + 1
    if not comments:
        raise AnalysisError(
            "No comments with analyzable text fit the input limits.", code="no_comments"
        )
    combined = "\n".join(texts)
    frequencies, keywords = word_statistics(combined)
    counts = {
        label: sum(c.sentiment == label for c in comments)
        for label in ("positive", "neutral", "negative")
    }
    warnings = [
        "Sample: recent public top-level comments in API time order; replies are excluded.",
        "Each analyzed comment counts once. Long comments use majority segment sentiment; "
        "ties use summed model scores. The displayed score averages winning-label scores.",
        "Comments may contain other languages; this model is intended for Indonesian.",
        "These are sampled audience responses, not population opinion. Scores are not calibrated.",
    ]
    if skipped:
        warnings.append(f"Skipped {skipped} comments without words or exceeding processing limits.")
    return AnalysisResult(
        source=SourceInfo(
            kind="youtube",
            url=f"https://www.youtube.com/watch?v={video_id}",
            title=f"YouTube comments · {video_id}",
            youtube_mode="comments",
            comment_order="time",
            comments_fetched=len(fetched),
        ),
        analyzed_at=datetime.now(timezone.utc),
        model=settings.model_name,
        model_revision=getattr(engine, "resolved_revision", settings.model_revision),
        character_count=len(combined),
        summary=SentimentSummary(
            total_segments=len(segments),
            unit="comments",
            total_units=len(comments),
            counts=counts,
            percentages={
                label: round(count / len(comments) * 100, 2) for label, count in counts.items()
            },
        ),
        segments=segments,
        comments=comments,
        keywords=[TermCount(term=term, count=count) for term, count in keywords],
        word_frequencies=frequencies,
        warnings=warnings,
    )
