"""Ambil top-level comments publik menggunakan YouTube Data API resmi."""

import httpx

from karhutla.errors import AnalysisError
from karhutla.extraction import youtube_video_id
from karhutla.text import clean_text


def fetch_comments(url: str, api_key: str, limit: int = 100) -> tuple[str, list[dict]]:
    video_id = youtube_video_id(url)
    if not api_key:
        raise AnalysisError(
            "Set YOUTUBE_API_KEY in .env and restart the API to analyze comments.",
            status_code=503,
            code="youtube_key_missing",
        )
    comments = []
    seen = set()
    token = None
    try:
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            # Batasi pagination, termasuk halaman kosong atau yang tidak sesuai perkiraan.
            for _ in range(5):
                params = {
                    "part": "snippet",
                    "videoId": video_id,
                    "maxResults": min(100, limit - len(comments)),
                    "order": "time",
                    "textFormat": "plainText",
                }
                if token:
                    params["pageToken"] = token
                # Jangan sertakan credential di URL, termasuk pada error log dan access log.
                response = client.get(
                    "https://www.googleapis.com/youtube/v3/commentThreads",
                    params=params,
                    headers={"X-Goog-Api-Key": api_key},
                )
                if response.status_code != 200:
                    try:
                        reasons = [
                            item.get("reason")
                            for item in response.json().get("error", {}).get("errors", [])
                        ]
                    except ValueError:
                        reasons = []
                    if "commentsDisabled" in reasons:
                        message, code = "Comments are disabled for this video.", "comments_disabled"
                    elif "quotaExceeded" in reasons or response.status_code == 429:
                        message, code = (
                            "YouTube API quota is exhausted. Try again later.",
                            "youtube_quota",
                        )
                    elif response.status_code == 404:
                        message, code = (
                            "The video was not found or is unavailable.",
                            "video_unavailable",
                        )
                    else:
                        message = (
                            "YouTube rejected the request. Check that the API key is valid, "
                            "YouTube Data API v3 is enabled, and key restrictions "
                            "allow this backend."
                        )
                        code = "youtube_api_rejected"
                    raise AnalysisError(message, code=code)
                payload = response.json()
                for item in payload.get("items", []):
                    comment = item["snippet"]["topLevelComment"]
                    snippet = comment["snippet"]
                    if comment["id"] in seen:
                        continue
                    seen.add(comment["id"])
                    comments.append(
                        {
                            "comment_id": comment["id"],
                            "text": clean_text(snippet.get("textDisplay", "")),
                            "like_count": snippet.get("likeCount", 0),
                            "published_at": snippet.get("publishedAt", ""),
                        }
                    )
                    if len(comments) >= limit:
                        break
                token = payload.get("nextPageToken")
                if len(comments) >= limit or not token:
                    break
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise AnalysisError(
            "YouTube comments could not be retrieved. Check your connection and try again.",
            code="comments_unavailable",
        ) from exc
    if not comments:
        raise AnalysisError("No public top-level comments were found.", code="no_comments")
    return video_id, comments
