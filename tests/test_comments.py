import httpx
import pytest

from karhutla.analysis import analyze_request
from karhutla.comments import fetch_comments
from karhutla.config import Settings
from karhutla.errors import AnalysisError
from karhutla.schemas import AnalyzeRequest


def test_key_is_required_and_hidden_from_settings_repr():
    assert "secret-value" not in repr(Settings(youtube_api_key="secret-value"))
    with pytest.raises(AnalysisError) as error:
        fetch_comments("https://youtu.be/abcdefghijk", "")
    assert error.value.code == "youtube_key_missing"


def test_pagination_and_key_header(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.headers["X-Goog-Api-Key"] == "test-only-secret"
        assert "test-only-secret" not in str(request.url)
        assert request.url.params["order"] == "time"
        number = len(calls)
        body = {
            "items": [
                {
                    "snippet": {
                        "topLevelComment": {
                            "id": f"comment_{number}",
                            "snippet": {
                                "textDisplay": "Saya senang.",
                                "likeCount": 2,
                                "publishedAt": "2026-10-18T00:00:00Z",
                            },
                        }
                    }
                }
            ]
        }
        if number == 1:
            body["nextPageToken"] = "page2"
        else:
            assert request.url.params["pageToken"] == "page2"
        return httpx.Response(200, json=body)

    original = httpx.Client
    monkeypatch.setattr(
        "karhutla.comments.httpx.Client",
        lambda **kw: original(
            transport=httpx.MockTransport(handler),
            **kw,
        ),
    )
    video_id, comments = fetch_comments("https://youtu.be/abcdefghijk", "test-only-secret", 2)
    assert video_id == "abcdefghijk"
    assert len(comments) == 2
    assert len(calls) == 2


@pytest.mark.parametrize(
    "reason,code",
    [
        ("commentsDisabled", "comments_disabled"),
        ("quotaExceeded", "youtube_quota"),
        ("keyInvalid", "youtube_api_rejected"),
    ],
)
def test_youtube_errors_never_expose_key(monkeypatch, reason, code):
    original = httpx.Client
    monkeypatch.setattr(
        "karhutla.comments.httpx.Client",
        lambda **kw: original(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    403,
                    json={"error": {"errors": [{"reason": reason}], "message": "secret-value"}},
                )
            ),
            **kw,
        ),
    )
    with pytest.raises(AnalysisError) as error:
        fetch_comments("https://youtu.be/abcdefghijk", "secret-value")
    assert error.value.code == code
    assert "secret-value" not in str(error.value)


def test_comment_summary_counts_each_comment_once(monkeypatch, fake_engine):
    monkeypatch.setattr(
        "karhutla.comments.fetch_comments",
        lambda *args: (
            "abcdefghijk",
            [
                {
                    "comment_id": "one",
                    "text": "Saya senang. Senang sekali.",
                    "like_count": 5,
                    "published_at": "2026-10-18T00:00:00Z",
                },
                {
                    "comment_id": "two",
                    "text": "Warga kecewa.",
                    "like_count": 1,
                    "published_at": "2026-10-18T00:00:00Z",
                },
                {"comment_id": "three", "text": "🔥🔥", "like_count": 0, "published_at": ""},
            ],
        ),
    )
    result = analyze_request(
        AnalyzeRequest(url="https://youtu.be/abcdefghijk", youtube_mode="comments"),
        fake_engine,
        Settings(),
    )
    assert result.summary.total_units == 2
    assert result.summary.total_segments == 3
    assert result.summary.unit == "comments"
    assert result.summary.percentages["positive"] == 50
    assert len(result.comments) == 2
    assert result.segments[-1].comment_id == "two"
    assert result.source.comments_fetched == 3
    assert any("Skipped 1" in warning for warning in result.warnings)


def test_comments_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        "karhutla.comments.fetch_comments",
        lambda *args: (
            "abcdefghijk",
            [
                {
                    "comment_id": "one",
                    "text": "Saya senang.",
                    "like_count": 1,
                    "published_at": "2026-10-18T00:00:00Z",
                }
            ],
        ),
    )
    response = client.post(
        "/analyze",
        json={
            "url": "https://youtu.be/abcdefghijk",
            "youtube_mode": "comments",
            "max_comments": 10,
        },
    )
    assert response.status_code == 200
    assert response.json()["comments"][0]["sentiment"] == "positive"


@pytest.mark.parametrize(
    "payload",
    [
        {"text": "Saya senang.", "youtube_mode": "comments"},
        {"url": "https://youtu.be/abcdefghijk", "max_comments": 101},
    ],
)
def test_comment_request_validation(client, payload):
    assert client.post("/analyze", json=payload).status_code == 422
