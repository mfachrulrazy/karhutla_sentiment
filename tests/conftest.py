import re

import pytest

from karhutla.text import sentence_spans


class FakeEngine:
    """Test double deterministik yang tidak digunakan oleh aplikasi saat berjalan."""

    loaded = False

    def analyze(self, text):
        self.loaded = True
        results = []
        for start, end in sentence_spans(text):
            sentence = text[start:end]
            lower = sentence.lower()
            label = (
                "positive" if "senang" in lower else "negative" if "kecewa" in lower else "neutral"
            )
            results.append(
                {
                    "text": sentence,
                    "char_start": start,
                    "char_end": end,
                    "sentiment": label,
                    "score": 0.8,
                }
            )
        return results


class WhitespaceTokenizer:
    """Offset yang dapat diprediksi untuk menguji cakupan chunk tanpa mengunduh tokenizer."""

    def __call__(self, text, **kwargs):
        offsets = [match.span() for match in re.finditer(r"\S+", text)]
        return {"offset_mapping": offsets, "input_ids": list(range(len(offsets)))}


@pytest.fixture
def fake_engine():
    return FakeEngine()


@pytest.fixture
def client(fake_engine):
    from fastapi.testclient import TestClient

    from karhutla.api import app
    from karhutla.model import get_engine

    app.dependency_overrides[get_engine] = lambda: fake_engine
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
