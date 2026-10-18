"""Pembersihan teks dan penghitungan keyword sederhana tanpa mengubah makna input model."""

import re
import unicodedata
from collections import Counter

# Stopword list singkat yang dapat diedit. HANYA digunakan untuk menghitung kata.
STOPWORDS = set(
    """
ada adalah adanya agar akan aku anda antara apa apabila atas atau bagi bahwa banyak
baru bawah beberapa begitu belum berbagai bersama bisa bukan dalam dan dari daripada
dengan dia di dilakukan juga hal hanya hari hingga ia ini itu jadi jika juga karena
kata ke kepada ketika kita lagi lain lebih maka masih maupun melalui memang menjadi
mereka merupakan oleh pada para paling pun saat saja salah sama sampai sangat satu
saya kami kamu sebagai sebelum sebuah sudah setelah setiap serta sejak seperti suatu telah
tentang tersebut tetapi tidak tiga telah terhadap terus untuk yaitu yakni yang
tak namun sebuah semua tahun bulan ujar ucap tutur menurut mengatakan menyebut
com www http https video channel subscribe like share ya nah eh oh si sang
""".split()
)


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    # Pertahankan tanda baca, kapitalisasi, negasi, dan batas paragraf untuk model.
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Kembalikan offset teks yang dibersihkan tanpa menghilangkan isi non-whitespace."""
    spans = []
    for match in re.finditer(r"\S.*?(?:(?<=[.!?])(?=\s)|(?=\n)|$)", text):
        start, end = match.span()
        if text[start:end].strip():
            spans.append((start, end))
    return spans


def token_chunks(text: str, tokenizer, max_tokens: int) -> list[tuple[int, int]]:
    """Pisahkan kalimat panjang pada batas token agar teks tidak terpotong tanpa pemberitahuan."""
    if max_tokens < 1:
        raise ValueError("max_tokens must be positive")

    def encode(value):
        return tokenizer(
            value,
            add_special_tokens=False,
            return_offsets_mapping=True,
            truncation=False,
            verbose=False,
        )["offset_mapping"]

    spans = []
    for start, end in sentence_spans(text):
        chunk_start = start
        while chunk_start < end:
            offsets = encode(text[chunk_start:end])
            if not offsets:
                break
            chunk_end = end if len(offsets) <= max_tokens else chunk_start + offsets[max_tokens][0]
            # Tokenisasi ulang prefix dapat mengubah batas BPE. Periksa jumlah token sebenarnya.
            while chunk_end > chunk_start and len(encode(text[chunk_start:chunk_end])) > max_tokens:
                chunk_end -= 1
            if chunk_end <= chunk_start:
                raise ValueError("A character cannot fit within the model's token budget")
            next_start = chunk_end
            while chunk_start < chunk_end and text[chunk_start].isspace():
                chunk_start += 1
            while chunk_end > chunk_start and text[chunk_end - 1].isspace():
                chunk_end -= 1
            if chunk_end > chunk_start:
                spans.append((chunk_start, chunk_end))
            chunk_start = next_start
            while chunk_start < end and text[chunk_start].isspace():
                chunk_start += 1
    return spans


def word_statistics(text: str) -> tuple[dict[str, int], list[tuple[str, int]]]:
    words: Counter = Counter()
    phrases: Counter = Counter()
    for start, end in sentence_spans(text):
        tokens = re.findall(r"[^\W\d_]+", text[start:end].lower())

        def meaningful(token):
            return len(token) >= 3 and token not in STOPWORDS

        words.update(token for token in tokens if meaningful(token))
        phrases.update(
            f"{left} {right}"
            for left, right in zip(tokens, tokens[1:])
            if meaningful(left) and meaningful(right)
        )
    # Utamakan frasa berulang; isi slot keyword yang tersisa dengan kata yang sering muncul.
    keywords = [(term, count) for term, count in phrases.most_common(10) if count >= 2]
    keywords.extend(words.most_common(15 - len(keywords)))
    return dict(words.most_common(200)), keywords
