import pytest

from karhutla.config import Settings
from karhutla.errors import AnalysisError


def test_health_does_not_load_the_model(client):
    assert client.get("/health").json() == {"status": "ok", "model_loaded": False}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"text": " "},
        {"text": "Kalimat", "url": "https://example.com"},
        {"text": "12345!!!"},
    ],
)
def test_reject_invalid_inputs(client, payload):
    assert client.post("/analyze", json=payload).status_code == 422


def test_text_analysis_and_distribution(client):
    response = client.post("/analyze", json={"text": "Saya senang. Warga kecewa. Tim datang."})
    assert response.status_code == 200
    body = response.json()
    assert body["source"]["kind"] == "text"
    assert body["summary"]["total_segments"] == 3
    assert body["summary"]["counts"] == {"positive": 1, "neutral": 1, "negative": 1}
    assert len(body["segments"]) == 3
    assert body["segments"][1]["sentiment"] == "negative"
    assert body["word_frequencies"]["warga"] == 1
    assert "calibrated" in " ".join(body["warnings"])


def test_api_reports_expected_model_failure(client, fake_engine, monkeypatch):
    def fail(text):
        raise AnalysisError("Download unavailable", status_code=503, code="model_unavailable")

    monkeypatch.setattr(fake_engine, "analyze", fail)
    response = client.post("/analyze", json={"text": "Petugas datang."})
    assert response.status_code == 503
    assert response.json()["code"] == "model_unavailable"
    assert "summary" not in response.json()


def test_api_rejects_oversized_text_before_inference(client, fake_engine, monkeypatch):
    monkeypatch.setattr("karhutla.api.get_settings", lambda: Settings(max_text_characters=10))
    response = client.post("/analyze", json={"text": "Teks ini terlalu panjang."})
    assert response.status_code == 422
    assert response.json()["code"] == "input_too_large"
    assert not fake_engine.loaded


def test_unsupported_publisher_has_paste_fallback(client):
    response = client.post("/analyze", json={"url": "https://example.com/story"})
    assert response.status_code == 422
    assert response.json()["code"] == "unsupported_source"
    assert "paste" in response.json()["detail"]


def test_caption_predictions_keep_timestamps(client, monkeypatch):
    from karhutla.extraction import ExtractedContent, TranscriptCue
    from karhutla.schemas import SourceInfo

    content = ExtractedContent(
        text="Saya senang. Warga kecewa.",
        source=SourceInfo(kind="youtube"),
        cues=[TranscriptCue(0, 12, 1.0, 3.0), TranscriptCue(13, 26, 3.0, 6.0)],
    )
    monkeypatch.setattr("karhutla.analysis.extract_url", lambda url: content)
    body = client.post("/analyze", json={"url": "https://youtu.be/abcdefghijk"}).json()
    assert body["segments"][0]["start_seconds"] == 1.0
    assert body["segments"][1]["end_seconds"] == 6.0
