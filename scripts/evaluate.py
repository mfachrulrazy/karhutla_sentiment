"""Evaluasi data CSV berlabel manual menggunakan model yang sama dengan API."""

import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix

from karhutla.config import get_settings
from karhutla.model import get_engine

LABELS = ["positive", "neutral", "negative"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "csv", type=Path, help="CSV with text, label, source_group, source_type, split"
    )
    parser.add_argument("--split", choices=["dev", "test"], default="test")
    parser.add_argument("--output", type=Path, default=Path("evaluation_results"))
    args = parser.parse_args()
    frame = pd.read_csv(args.csv, dtype=str).fillna("")
    required = {"text", "label", "source_group", "source_type", "split"}
    if not required.issubset(frame.columns):
        parser.error(f"Missing columns: {', '.join(sorted(required - set(frame.columns)))}")
    if not frame["split"].isin(["dev", "test"]).all():
        parser.error("Every row must have split=dev or split=test.")
    if not frame["source_type"].isin(["news", "youtube"]).all():
        parser.error("Every row must have source_type=news or source_type=youtube.")
    if (frame["source_group"].str.strip() == "").any():
        parser.error("Every row needs a source_group identifying its article or video.")
    if (frame.groupby("source_group")["split"].nunique() > 1).any():
        parser.error("An article/video source_group cannot appear in both dev and test.")
    frame = frame.loc[frame["split"] == args.split].copy()
    if frame.empty:
        parser.error(f"No rows found for split={args.split}.")
    if not frame["label"].isin(LABELS).all() or (frame["text"].str.strip() == "").any():
        parser.error("Use non-empty text and labels positive, neutral, or negative.")
    engine = get_engine()
    predicted = []
    for text in frame["text"]:
        results = engine.analyze(text)
        if len(results) != 1:
            parser.error("Each evaluation row must contain one sentence or short model segment.")
        predicted.append(results[0]["sentiment"])
    frame["predicted"] = predicted
    settings = get_settings()
    report = {
        "model": settings.model_name,
        "revision": engine.resolved_revision,
        "split": args.split,
        "rows": len(frame),
        "overall": classification_report(
            frame.label,
            predicted,
            labels=LABELS,
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix_labels": LABELS,
        "confusion_matrix": confusion_matrix(frame.label, predicted, labels=LABELS).tolist(),
        "by_source_type": {},
    }
    for source_type, group in frame.groupby("source_type"):
        report["by_source_type"][source_type] = classification_report(
            group.label,
            group.predicted,
            labels=LABELS,
            output_dict=True,
            zero_division=0,
        )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    frame.to_csv(args.output / "predictions.csv", index=False)
    print(classification_report(frame.label, predicted, labels=LABELS, zero_division=0))
    print(f"Report and predictions saved to {args.output.resolve()}")


if __name__ == "__main__":
    main()
