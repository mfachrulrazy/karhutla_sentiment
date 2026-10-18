from karhutla import dashboard_backend
from karhutla.config import Settings


def test_direct_mode_needs_no_api_server(monkeypatch, fake_engine):
    monkeypatch.setenv("ANALYSIS_MODE", "direct")
    monkeypatch.setattr(dashboard_backend, "get_engine", lambda: fake_engine)
    monkeypatch.setattr(dashboard_backend, "get_settings", lambda: Settings())
    result = dashboard_backend.analyze_payload({"text": "Saya senang."}, "http://unreachable")
    assert result["summary"]["counts"]["positive"] == 1
    assert isinstance(result["analyzed_at"], str)


def test_dashboard_direct_mode_renders(monkeypatch, fake_engine):
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("ANALYSIS_MODE", "direct")
    monkeypatch.setattr(dashboard_backend, "get_engine", lambda: fake_engine)
    monkeypatch.setattr(dashboard_backend, "get_settings", lambda: Settings())
    dashboard = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"),
        default_timeout=60,
    ).run()
    next(b for b in dashboard.button if b.label == "Load sample text").click().run()
    next(b for b in dashboard.button if b.label == "Analyze sentiment").click().run()
    assert not dashboard.exception
    assert len(dashboard.metric) == 3
