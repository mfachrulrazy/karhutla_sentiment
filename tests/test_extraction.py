import socket
from types import SimpleNamespace

import httpx
import pytest

from karhutla.errors import AnalysisError
from karhutla.extraction import (
    extract_news,
    extract_youtube,
    hostname_matches,
    validate_public_host,
    validate_url,
    youtube_video_id,
)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://user:password@kompas.com/",
        "https://kompas.com:8080/",
        "https://",
        "not a url",
    ],
)
def test_invalid_urls_rejected(url):
    with pytest.raises(AnalysisError):
        validate_url(url)


def test_domain_checks_require_a_real_subdomain():
    assert hostname_matches("regional.kompas.com", ("kompas.com",))
    assert not hostname_matches("evilkompas.com", ("kompas.com",))
    assert not hostname_matches("kompas.com.evil.test", ("kompas.com",))


def test_private_dns_addresses_are_rejected(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0)),
        ],
    )
    with pytest.raises(AnalysisError, match="public"):
        validate_public_host("kompas.com")


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=abcdefghijk&t=12",
        "https://youtu.be/abcdefghijk",
        "https://youtube.com/shorts/abcdefghijk",
        "https://youtube.com/live/abcdefghijk",
    ],
)
def test_youtube_url_forms(url):
    assert youtube_video_id(url) == "abcdefghijk"


def test_youtube_channel_is_not_a_video():
    with pytest.raises(AnalysisError):
        youtube_video_id("https://youtube.com/@channel")


def mock_news_client(monkeypatch, handler):
    original_client = httpx.Client
    monkeypatch.setattr(
        "karhutla.extraction.httpx.Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    monkeypatch.setattr("karhutla.extraction.validate_public_host", lambda host: None)


def test_real_html_extractor_on_local_fixture(monkeypatch):
    html = """<html lang="id"><head><title>Kebakaran Kalimantan</title></head><body>
    <article><h1>Kebakaran Kalimantan</h1>
    <p>Kebakaran hutan dan lahan melanda sejumlah desa di Kalimantan. Petugas membawa
    bantuan untuk masyarakat yang terdampak asap tebal di wilayah tersebut.</p>
    <p>Warga mengapresiasi kerja keras petugas dalam memadamkan api. Tim gabungan
    terus bekerja di lapangan untuk mencegah kebakaran meluas ke permukiman.</p>
    </article></body></html>"""
    mock_news_client(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            text=html,
            headers={"content-type": "text/html; charset=utf-8"},
        ),
    )
    content = extract_news("https://www.antaranews.com/berita/test")
    assert content.source.kind == "news"
    assert "Warga mengapresiasi" in content.text
    assert content.source.title == "Kebakaran Kalimantan"


def test_redirect_to_unsupported_host_is_rejected(monkeypatch):
    mock_news_client(
        monkeypatch,
        lambda request: httpx.Response(
            302,
            headers={"location": "http://127.0.0.1/admin"},
        ),
    )
    with pytest.raises(AnalysisError) as error:
        extract_news("https://kompas.com/story")
    assert error.value.code == "unsupported_source"


def test_caption_extraction_uses_indonesian_and_builds_offsets(monkeypatch):
    from youtube_transcript_api import YouTubeTranscriptApi

    class Transcript(list):
        is_generated = True

    def fetch(self, video_id, languages):
        assert video_id == "abcdefghijk"
        assert languages == ["id"]
        return Transcript(
            [
                SimpleNamespace(text="Warga   senang.", start=1.0, duration=2.0),
                SimpleNamespace(text="Bantuan datang.", start=4.0, duration=3.0),
            ]
        )

    monkeypatch.setattr(YouTubeTranscriptApi, "fetch", fetch)
    content = extract_youtube("https://youtu.be/abcdefghijk")
    assert content.text == "Warga senang. Bantuan datang."
    assert content.source.transcript_generated is True
    assert content.text[content.cues[1].char_start : content.cues[1].char_end] == "Bantuan datang."
    assert content.cues[1].end_seconds == 7.0
