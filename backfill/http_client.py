"""Client HTTP avec délai, reprise sur 429 et retries transitoires."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

logger = logging.getLogger(__name__)

RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}


class RateLimitedClient:
    def __init__(
        self,
        *,
        delay_s: float = 0.0,
        timeout_s: float = 45.0,
        headers: dict[str, str] | None = None,
        auth: httpx.Auth | tuple[str, str] | None = None,
        header_provider: Callable[[], dict[str, str]] | None = None,
        max_retries: int = 5,
        user_agent: str = "corridor-cd-backfill/0.1",
    ) -> None:
        self.delay_s = delay_s
        self.timeout_s = timeout_s
        self.headers = {"User-Agent": user_agent, **(headers or {})}
        self.auth = auth
        self.header_provider = header_provider
        self.max_retries = max_retries
        self._last_request_at = 0.0

    def _wait_delay(self) -> None:
        if self.delay_s <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self.delay_s - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        empty_on_404: bool = False,
    ) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            self._wait_delay()
            extra = self.header_provider() if self.header_provider else {}
            headers = {**self.headers, **extra}
            try:
                response = httpx.request(
                    method,
                    url,
                    params=params,
                    headers=headers,
                    auth=self.auth,
                    timeout=self.timeout_s,
                    follow_redirects=True,
                )
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning("HTTP erreur %s %s (%s), tentative %s", method, url, exc, attempt + 1)
                time.sleep(min(60.0, 2 ** attempt))
                continue
            self._last_request_at = time.monotonic()
            if response.status_code == 404 and empty_on_404:
                return response
            if response.status_code in RETRY_STATUS:
                retry_after = response.headers.get("X-Rate-Limit-Retry-After-Seconds") or response.headers.get(
                    "Retry-After"
                )
                wait_s = float(retry_after) if retry_after else min(90.0, 5 * (2 ** attempt))
                logger.warning(
                    "HTTP %s sur %s, attente %.0fs (tentative %s)",
                    response.status_code,
                    url,
                    wait_s,
                    attempt + 1,
                )
                if wait_s > 6 * 3600:
                    response.raise_for_status()
                time.sleep(wait_s)
                last_error = httpx.HTTPStatusError(
                    f"{response.status_code}", request=response.request, response=response
                )
                continue
            response.raise_for_status()
            return response
        if last_error:
            raise last_error
        raise RuntimeError(f"échec HTTP {method} {url}")

    def get_bytes(self, url: str, *, params: dict[str, Any] | None = None) -> bytes:
        return self.request("GET", url, params=params).content

    def get_text(self, url: str, *, params: dict[str, Any] | None = None) -> str:
        return self.request("GET", url, params=params).text

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        empty_on_404: bool = False,
    ) -> Any:
        response = self.request("GET", url, params=params, empty_on_404=empty_on_404)
        if response.status_code == 404:
            return []
        if not response.content:
            return []
        return response.json()
