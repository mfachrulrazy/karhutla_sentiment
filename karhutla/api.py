"""Jalankan dengan: uvicorn karhutla.api:app --reload --host 127.0.0.1"""

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from karhutla.analysis import analyze_request
from karhutla.config import get_settings
from karhutla.errors import AnalysisError
from karhutla.model import get_engine
from karhutla.schemas import AnalysisResult, AnalyzeRequest

app = FastAPI(
    title="Karhutla Sentiment API",
    description="Local Indonesian news, YouTube transcript, and text sentiment analysis.",
    version="0.1.0",
    license_info={"name": "MIT"},
)


@app.exception_handler(AnalysisError)
def analysis_error_handler(request: Request, exc: AnalysisError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc), "code": exc.code},
    )


@app.get("/health")
def health(engine=Depends(get_engine)):
    """Hanya memeriksa liveness; tidak mengunduh model atau menyatakan kesiapan inference."""
    return {"status": "ok", "model_loaded": engine.loaded}


@app.post("/analyze", response_model=AnalysisResult)
def analyze(payload: AnalyzeRequest, engine=Depends(get_engine)):
    return analyze_request(payload, engine, get_settings())
