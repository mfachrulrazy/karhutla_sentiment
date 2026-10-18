"""Ambil halaman berita publik yang didukung dan caption YouTube berbahasa Indonesia."""

import ipaddress
import socket
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urljoin, urlsplit

import httpx
import requests
import trafilatura

from karhutla.errors import AnalysisError
from karhutla.schemas import SourceInfo

# Mulai dengan beberapa penerbit yang ditentukan. Tambahkan domain setelah menguji extraction.
NEWS_DOMAINS = ("kompas.com", "antaranews.com", "detik.com")
YOUTUBE_DOMAINS = ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be")
MAX_DOWNLOAD_BYTES = 3_000_000


@dataclass
class TranscriptCue:
    char_start: int
    char_end: int
    start_seconds: float
    end_seconds: float


@dataclass
class ExtractedContent:
    text: str
    source: SourceInfo
    warnings: list[str] = field(default_factory=list)
    cues: list[TranscriptCue] = field(default_factory=list)


def hostname_matches(hostname: str, domains: tuple[str, ...]) -> bool:
    return any(hostname == domain or hostname.endswith("." + domain) for domain in domains)


def validate_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise AnalysisError("The URL is invalid.", code="invalid_url") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 80, 443}
    ):
        raise AnalysisError(
            "Use a public HTTP or HTTPS URL without credentials or custom ports.",
            code="invalid_url",
        )
    return parsed.hostname.lower()


def validate_public_host(host: str) -> None:
    """Tolak tujuan private/lokal, termasuk redirect, sebelum mengambil berita."""
    try:
        addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise AnalysisError(
            "The news website could not be reached. Try pasting the article text.",
            code="source_unavailable",
        ) from exc
    if not addresses or any(
        not ipaddress.ip_address(address[4][0]).is_global for address in addresses
    ):
        raise AnalysisError("Only public websites are supported.", code="invalid_url")


def youtube_video_id(url: str) -> str:
    import re

    host = validate_url(url)
    if host not in YOUTUBE_DOMAINS:
        raise AnalysisError("Use a supported YouTube video URL.", code="invalid_url")
    parsed = urlsplit(url)
    parts = parsed.path.strip("/").split("/")
    if host == "youtu.be":
        video_id = parts[0]
    elif parsed.path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [""])[0]
    elif len(parts) == 2 and parts[0] in {"shorts", "embed", "live"}:
        video_id = parts[1]
    else:
        video_id = ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise AnalysisError(
            "Use a YouTube video link, rather than a channel or playlist link.",
            code="invalid_url",
        )
    return video_id


def extract_youtube(url: str) -> ExtractedContent:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api._errors import YouTubeTranscriptApiException

    video_id = youtube_video_id(url)
    try:
        # Tanpa penerjemahan: model ditujukan untuk teks berbahasa Indonesia.
        class TimeoutSession(requests.Session):
            def request(self, *args, **kwargs):
                kwargs.setdefault("timeout", 20)
                return super().request(*args, **kwargs)

        with TimeoutSession() as session:
            transcript = YouTubeTranscriptApi(http_client=session).fetch(video_id, languages=["id"])
    except (YouTubeTranscriptApiException, requests.RequestException) as exc:
        raise AnalysisError(
            "Indonesian captions could not be retrieved. They may be unavailable, or YouTube "
            "may have blocked the request. Paste the transcript using the Text option.",
            code="transcript_unavailable",
        ) from exc

    from karhutla.text import clean_text

    pieces = []
    cues = []
    offset = 0
    for snippet in transcript:
        piece = clean_text(snippet.text).replace("\n", " ")
        if not piece:
            continue
        pieces.append(piece)
        cues.append(
            TranscriptCue(
                offset, offset + len(piece), snippet.start, snippet.start + snippet.duration
            )
        )
        offset += len(piece) + 1
    warnings = [
        "This analyzes spoken content from captions, not YouTube audience comments.",
        "Caption punctuation and transcription errors can affect sentiment predictions.",
    ]
    if transcript.is_generated:
        warnings.append("The transcript was generated automatically by YouTube.")
    return ExtractedContent(
        text=" ".join(pieces),
        source=SourceInfo(
            kind="youtube",
            url=f"https://www.youtube.com/watch?v={video_id}",
            title=f"YouTube video {video_id}",
            transcript_generated=transcript.is_generated,
        ),
        warnings=warnings,
        cues=cues,
    )


def extract_news(url: str) -> ExtractedContent:
    current = url
    try:
        with httpx.Client(
            timeout=httpx.Timeout(20.0),
            follow_redirects=False,
            headers={"User-Agent": "KarhutlaSentiment/0.1 (local educational project)"},
        ) as client:
            for _ in range(4):
                host = validate_url(current)
                if not hostname_matches(host, NEWS_DOMAINS):
                    raise AnalysisError(
                        "Supported news publishers: kompas.com, antaranews.com, and detik.com. "
                        "For another publisher, paste the article text.",
                        code="unsupported_source",
                    )
                validate_public_host(host)
                with client.stream("GET", current) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise AnalysisError("The source returned an invalid redirect.")
                        current = urljoin(current, location)
                        continue
                    response.raise_for_status()
                    if "html" not in response.headers.get("content-type", "").lower():
                        raise AnalysisError("The news URL must point to an HTML article.")
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > MAX_DOWNLOAD_BYTES:
                            raise AnalysisError(
                                "This page is too large. Paste the article text instead.",
                                code="source_too_large",
                            )
                    html = bytes(data)
                    break
            else:
                raise AnalysisError("Too many redirects. Paste the article text instead.")
    except httpx.HTTPError as exc:
        raise AnalysisError(
            "The article could not be downloaded. It may be restricted or unavailable. "
            "Paste the article text instead.",
            code="source_unavailable",
        ) from exc

    document = trafilatura.bare_extraction(
        html,
        url=current,
        with_metadata=True,
        include_comments=False,
        include_tables=False,
    )
    if not document or not document.text or len(document.text.strip()) < 80:
        raise AnalysisError(
            "No readable article was found. Use a direct article URL or paste its text.",
            code="extraction_failed",
        )
    return ExtractedContent(
        text=document.text,
        source=SourceInfo(kind="news", url=current, title=document.title),
        warnings=["Extraction is best effort. Check that the preview contains the full article."],
    )


def extract_url(url: str) -> ExtractedContent:
    host = validate_url(url)
    if host in YOUTUBE_DOMAINS:
        return extract_youtube(url)
    return extract_news(url)
