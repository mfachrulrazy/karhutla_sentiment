"""Backend dashboard: analisis langsung untuk cloud atau request ke FastAPI."""

import os

import httpx

from karhutla.analysis import analyze_request
from karhutla.config import get_settings
from karhutla.errors import AnalysisError
from karhutla.model import get_engine
from karhutla.schemas import AnalyzeRequest


def analysis_mode() -> str:
    mode = os.getenv("ANALYSIS_MODE", "direct").lower()
    if mode not in {"direct", "api"}:
        raise AnalysisError("ANALYSIS_MODE must be direct or api.", code="invalid_configuration")
    return mode


def analyze_payload(payload: dict, api_url: str) -> dict:
    if analysis_mode() == "direct":
        result = analyze_request(AnalyzeRequest(**payload), get_engine(), get_settings())
        return result.model_dump(mode="json")
    response = httpx.post(f"{api_url}/analyze", json=payload, timeout=600)
    if response.is_success:
        return response.json()
    detail = response.json().get("detail", "Analysis failed.")
    if isinstance(detail, list):
        detail = "; ".join(item.get("msg", "Invalid input") for item in detail)
    raise AnalysisError(str(detail), status_code=response.status_code)
