"""
A shared HTTP client that every collector uses to call APIs.

Why not just call httpx.get() everywhere?
Because real APIs fail sometimes: slow network, "too many requests"
(429), or server errors (500-599). Here we handle that ONCE:
  - timeout, so we never wait forever
  - retry with backoff (wait 1s, 2s, 4s...) on temporary errors
  - a clear User-Agent so platforms know who is calling
Every collector gets this for free.
"""
from __future__ import annotations

import time

import httpx

from app.core.logger import get_logger

log = get_logger(__name__)

# These status codes mean "try again later", not "you did something wrong"
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class HttpClient:
    def __init__(self, timeout_seconds: float = 20, max_retries: int = 3):
        self.max_retries = max_retries
        self._client = httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "GameTracker/0.1 (learning project)"},
        )

    def get_json(self, url: str, params: dict | None = None) -> dict | list:
        """GET a URL and return the JSON body. Retries on temporary errors."""
        return self._request("GET", url, params=params).json()

    def post_form(self, url: str, data: dict, params: dict | None = None) -> str:
        """POST a form (like a website does) and return the raw text body. Retries on temporary errors."""
        return self._request("POST", url, params=params, data=data).text

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """One place for timeout + retry logic, used by every GET and POST."""
        attempt = 0
        while True:
            attempt += 1
            try:
                response = self._client.request(method, url, **kwargs)
                if response.status_code in RETRY_STATUS_CODES:
                    raise httpx.HTTPStatusError(
                        f"temporary error {response.status_code}", request=response.request, response=response
                    )
                response.raise_for_status()  # 4xx errors (our mistake) fail right away
                return response
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                is_temporary = isinstance(exc, httpx.TransportError) or (
                    exc.response.status_code in RETRY_STATUS_CODES
                )
                if not is_temporary or attempt > self.max_retries:
                    raise
                wait = 2 ** (attempt - 1)  # 1s, 2s, 4s ...
                log.warning("Request failed (%s). Retry %d/%d in %ds", exc, attempt, self.max_retries, wait)
                time.sleep(wait)

    def close(self) -> None:
        self._client.close()

    # Lets us write: with HttpClient() as http: ...
    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *_) -> None:
        self.close()
