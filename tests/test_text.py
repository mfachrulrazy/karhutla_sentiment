import re

from conftest import WhitespaceTokenizer

from karhutla.text import clean_text, sentence_spans, token_chunks, word_statistics


def test_cleanup_preserves_negation_and_punctuation():
    assert clean_text("  Ini\tTIDAK   efektif!\n\nAsap tebal. ") == (
        "Ini TIDAK efektif!\n\nAsap tebal."
    )


def test_sentence_spans_cover_all_non_whitespace():
    text = 'Asap tebal. "Petugas datang!"\nWarga menunggu? Ya, belum selesai'
    recovered = "".join(text[start:end] for start, end in sentence_spans(text))
    assert re.sub(r"\s", "", recovered) == re.sub(r"\s", "", text)


def test_long_sentence_is_split_without_losing_content():
    text = " ".join(f"kata{number}" for number in range(123))
    chunks = token_chunks(text, WhitespaceTokenizer(), max_tokens=10)
    assert len(chunks) == 13
    assert " ".join(text[start:end] for start, end in chunks) == text
    assert all(len(text[start:end].split()) <= 10 for start, end in chunks)


def test_word_counts_filter_stopwords_and_preserve_repeated_phrases():
    text = "Kebakaran hutan terjadi. Kebakaran hutan dan asap. Tidak efektif!"
    frequencies, keywords = word_statistics(text)
    assert frequencies["kebakaran"] == 2
    assert "dan" not in frequencies
    assert "tidak" not in frequencies
    assert ("kebakaran hutan", 2) in keywords
    # Penghitungan statistik tidak mengubah teks yang digunakan untuk sentiment analysis.
    assert "Tidak" in text
