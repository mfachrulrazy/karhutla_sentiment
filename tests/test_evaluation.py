import json

import pandas as pd
import pytest

from karhutla.config import Settings
from scripts import evaluate


def test_evaluation_writes_metrics_and_predictions(tmp_path, monkeypatch, fake_engine):
    dataset = tmp_path / "labels.csv"
    output = tmp_path / "results"
    pd.DataFrame(
        [
            {
                "text": "Saya senang.",
                "label": "positive",
                "source_group": "article_1",
                "source_type": "news",
                "split": "test",
            },
            {
                "text": "Warga kecewa.",
                "label": "negative",
                "source_group": "video_1",
                "source_type": "youtube",
                "split": "test",
            },
        ]
    ).to_csv(dataset, index=False)
    fake_engine.resolved_revision = "test-only"
    monkeypatch.setattr(evaluate, "get_engine", lambda: fake_engine)
    monkeypatch.setattr(evaluate, "get_settings", lambda: Settings(model_name="test-only"))
    monkeypatch.setattr("sys.argv", ["evaluate.py", str(dataset), "--output", str(output)])
    evaluate.main()
    report = json.loads((output / "report.json").read_text())
    assert report["model"] == "test-only"
    assert report["rows"] == 2
    assert set(report["by_source_type"]) == {"news", "youtube"}
    assert sum(map(sum, report["confusion_matrix"])) == 2
    assert (output / "predictions.csv").exists()


def test_evaluation_rejects_source_leakage(tmp_path, monkeypatch, fake_engine):
    dataset = tmp_path / "leaked.csv"
    pd.DataFrame(
        [
            {
                "text": "Saya senang.",
                "label": "positive",
                "source_group": "same_video",
                "source_type": "youtube",
                "split": split,
            }
            for split in ["dev", "test"]
        ]
    ).to_csv(dataset, index=False)
    monkeypatch.setattr("sys.argv", ["evaluate.py", str(dataset)])
    with pytest.raises(SystemExit) as error:
        evaluate.main()
    assert error.value.code == 2
    assert not fake_engine.loaded
