from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_dashboard_renders_sample_and_result(monkeypatch, client):
    import httpx

    monkeypatch.setenv("ANALYSIS_MODE", "api")

    # Arahkan dashboard ke API sebenarnya dengan model double khusus untuk test.
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, **kwargs: client.post(
            "/analyze",
            json=kwargs["json"],
        ),
    )
    dashboard = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "app.py"),
        default_timeout=60,
    )
    dashboard.run()
    assert not dashboard.exception
    next(button for button in dashboard.button if button.label == "Load sample text").click().run()
    assert "Kalimantan" in dashboard.text_area[0].value
    next(button for button in dashboard.button if button.label == "Analyze sentiment").click().run()
    assert not dashboard.exception
    assert len(dashboard.metric) == 3
    assert dashboard.session_state["result"]["source"]["kind"] == "text"
