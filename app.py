"""Dashboard untuk pemula: streamlit run app.py; mendukung mode direct dan API."""

import io
import os
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from karhutla.dashboard_backend import analysis_mode, analyze_payload
from karhutla.errors import AnalysisError
from karhutla.model import get_engine

load_dotenv()
# Baca secret cloud tanpa menyertakan nilainya dalam kode atau log.
try:
    cloud_secrets = st.secrets
    for name in (
        "YOUTUBE_API_KEY",
        "ANALYSIS_MODE",
        "API_URL",
        "MODEL_LOCAL_FILES_ONLY",
        "MODEL_CACHE_DIR",
        "SENTIMENT_MODEL",
        "SENTIMENT_MODEL_REVISION",
        "MAX_TEXT_CHARACTERS",
        "MAX_SEGMENTS",
    ):
        if name in cloud_secrets:
            os.environ[name] = str(cloud_secrets[name])
except FileNotFoundError:
    pass
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")
ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache" / "matplotlib"))

st.set_page_config(page_title="Karhutla Opinion Sentiment", page_icon="🌿", layout="wide")
st.title("🌿 Karhutla Opinion Sentiment")
st.write(
    "Telusuri berita, transkrip YouTube, dan komentar tentang kebakaran hutan "
    "dan lahan di Indonesia."
)

with st.sidebar:
    st.subheader("Tentang Proyek Ini")
    st.write("Satu masukan dalam satu waktu. Tiga label sentimen: positif, netral, dan negatif.")
    st.caption(
        "Model dijalankan secara lokal. Komentar YouTube menggunakan kunci YouTube Data API Anda."
    )
    st.caption("Sumber Berita: Kompas, Antara, dan Detik. YouTube: transkrip atau komentar publik.")
    if st.button("Cek Koneksi API"):
        try:
            if analysis_mode() == "direct":
                loaded = get_engine().loaded
                st.success("Mode direct aktif; tidak memerlukan server API terpisah.")
            else:
                response = httpx.get(f"{API_URL}/health", timeout=5)
                response.raise_for_status()
                loaded = response.json().get("model_loaded", False)
                st.success("API connected")
            st.caption("Model loaded." if loaded else "Model will load on the first analysis.")
        except (httpx.HTTPError, ValueError, AnalysisError):
            st.error("API unavailable. Follow the README to start the API server.")

mode = st.radio("Choose an input", ["Text", "News URL", "YouTube URL"], horizontal=True)
youtube_mode = "transcript"
max_comments = 100
if mode == "YouTube URL":
    youtube_choice = st.radio("Analyze", ["Comments", "Transcript"], horizontal=True)
    youtube_mode = youtube_choice.lower()
    if youtube_mode == "comments":
        max_comments = st.slider("Maximum recent comments", 10, 100, 50, step=10)
        st.caption("Public top-level comments only; replies are excluded. Start with 10–50.")
if mode == "Text":
    st.button(
        "Load sample text",
        on_click=lambda: st.session_state.update(
            input_text=(ROOT / "data" / "sample.txt").read_text(encoding="utf-8")
        ),
    )

with st.form("analysis_form"):
    if mode == "Text":
        value = st.text_area(
            "Indonesian article, transcript, or excerpt",
            height=200,
            key="input_text",
            placeholder="Paste Indonesian text here, or load the sample above.",
            max_chars=30_000,
        )
    else:
        value = st.text_input(
            "Article URL" if mode == "News URL" else "YouTube video URL",
            placeholder="https://…",
            key=f"url_{mode}",
        )
        st.caption("If extraction fails, choose Text and paste the article or transcript.")
    submitted = st.form_submit_button("Analyze sentiment", type="primary")

if submitted:
    if not value.strip():
        st.warning("Enter some text or a URL first.")
    else:
        payload = {"text" if mode == "Text" else "url": value.strip()}
        if mode == "YouTube URL":
            payload.update(youtube_mode=youtube_mode, max_comments=max_comments)
        with st.spinner("Analyzing… The first run downloads the model and can take a few minutes."):
            try:
                st.session_state["result"] = analyze_payload(payload, API_URL)
            except AnalysisError as exc:
                st.error(str(exc))
            except httpx.ConnectError:
                st.error("Could not connect to the API. Start it using the README instructions.")
            except httpx.TimeoutException:
                st.error("The request timed out. Check the API terminal and try a shorter excerpt.")
            except (httpx.HTTPError, ValueError):
                st.error("The API response could not be read. Check the API terminal.")

result = st.session_state.get("result")
if result:
    st.divider()
    st.subheader("Last successful analysis")
    source = result["source"]
    is_comments = source.get("youtube_mode") == "comments"
    unit = "comments" if is_comments else "segments"
    st.write(source.get("title") or "Pasted text")
    if source.get("url"):
        st.write(source["url"])
    st.caption(
        f"Source: {source['kind']} · {result['character_count']:,} characters · "
        f"{result['summary'].get('total_units') or result['summary']['total_segments']} "
        f"analyzed {unit} · "
        f"{result['analyzed_at']}"
    )
    for column, label in zip(st.columns(3), ["positive", "neutral", "negative"]):
        column.metric(
            label.title(),
            f"{result['summary']['percentages'][label]:.1f}%",
            help=f"{result['summary']['counts'][label]} {unit} predicted as {label}.",
        )
    st.caption(
        f"These percentages describe analyzed {unit}. They do not measure population opinion."
    )
    if is_comments:
        st.caption(
            f"Fetched {source['comments_fetched']} recent top-level comments, ordered by time."
        )

    chart_column, cloud_column = st.columns(2)
    with chart_column:
        st.subheader("Sentiment distribution")
        chart_data = pd.DataFrame(
            {
                "Sentiment": list(result["summary"]["counts"]),
                unit.title(): list(result["summary"]["counts"].values()),
            }
        ).set_index("Sentiment")
        st.bar_chart(chart_data, color="#39966c")
    with cloud_column:
        st.subheader("Word cloud")
        if result["word_frequencies"]:
            from wordcloud import WordCloud

            cloud = WordCloud(
                width=1000,
                height=450,
                background_color="white",
                colormap="viridis",
                collocations=False,
                random_state=42,
            ).generate_from_frequencies(result["word_frequencies"])
            image = cloud.to_image()
            st.image(image, width="stretch")
            image_buffer = io.BytesIO()
            image.save(image_buffer, format="PNG")
            st.download_button(
                "Download word cloud",
                image_buffer.getvalue(),
                "wordcloud.png",
                "image/png",
            )
        else:
            st.info("There are no meaningful words left after filtering common words.")

    st.subheader("Frequent keywords and phrases")
    st.dataframe(pd.DataFrame(result["keywords"]), hide_index=True, width="stretch")
    st.caption("Frequency indicates repetition, rather than importance or sentiment.")

    st.subheader("Comment predictions" if is_comments else "Segment predictions")
    labels = st.multiselect(
        "Show sentiments",
        ["positive", "neutral", "negative"],
        default=["positive", "neutral", "negative"],
    )
    frame = pd.DataFrame(result["comments"] if is_comments else result["segments"])
    display_columns = (
        ["text", "sentiment", "score", "like_count", "published_at"]
        if is_comments
        else ["id", "text", "sentiment", "score"]
    )
    if source["kind"] == "youtube" and not is_comments:
        display_columns += ["start_seconds", "end_seconds"]
    st.dataframe(
        frame.loc[frame.sentiment.isin(labels), display_columns],
        hide_index=True,
        width="stretch",
    )
    st.caption("The score is the model's output for its chosen label, not verified accuracy.")
    with st.expander("Extracted text preview"):
        st.text("\n".join(segment["text"] for segment in result["segments"]))
    with st.expander("Notes and model details"):
        for warning in result["warnings"]:
            st.write(f"• {warning}")
        st.caption(f"Model: {result['model']} · revision: {result['model_revision']}")

    import json

    left, right = st.columns(2)
    # Lakukan escaping pada prefix formula spreadsheet dalam teks sumber sebelum export CSV.
    export_frame = frame.copy()
    export_frame["text"] = export_frame["text"].map(
        lambda text: "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text
    )
    left.download_button(
        "Download predictions (CSV)",
        export_frame.to_csv(index=False).encode("utf-8-sig"),
        "sentiment.csv",
        "text/csv",
    )
    right.download_button(
        "Download complete results (JSON)",
        json.dumps(result, ensure_ascii=False, indent=2),
        "analysis.json",
        "application/json",
    )
