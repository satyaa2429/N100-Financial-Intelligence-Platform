"""FastAPI client used by the Streamlit dashboard."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE_URL = os.getenv(
    "N100_API_URL",
    "http://127.0.0.1:8000/api/v1",
)

DEFAULT_TIMEOUT = 10


class APIClientError(RuntimeError):
    """Raised when the dashboard cannot access the API."""


def api_get(
    endpoint: str,
    params: dict[str, Any] | None = None,
) -> Any:
    """Send a GET request to the FastAPI service."""

    endpoint = endpoint.strip()

    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint

    url = API_BASE_URL.rstrip("/") + endpoint

    if params:
        clean_params = {
            key: value
            for key, value in params.items()
            if value is not None
        }

        if clean_params:
            url += "?" + urlencode(
                clean_params
            )

    request = Request(
        url,
        method="GET",
        headers={
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(
            request,
            timeout=DEFAULT_TIMEOUT,
        ) as response:

            body = response.read().decode(
                "utf-8"
            )

            return json.loads(
                body
            )

    except HTTPError as exc:
        raise APIClientError(
            f"API returned HTTP "
            f"{exc.code}: {url}"
        ) from exc

    except URLError as exc:
        raise APIClientError(
            "FastAPI server is unavailable. "
            "Start it on port 8000."
        ) from exc

    except json.JSONDecodeError as exc:
        raise APIClientError(
            "API returned invalid JSON."
        ) from exc


def get_health() -> dict:
    """Return FastAPI health information."""

    result = api_get(
        "/health"
    )

    if not isinstance(
        result,
        dict,
    ):
        raise APIClientError(
            "Invalid health response."
        )

    return result


def get_companies(
    sector: str | None = None,
    search: str | None = None,
) -> list[dict]:
    """Return companies from FastAPI."""

    result = api_get(
        "/companies",
        {
            "sector": sector,
            "search": search,
        },
    )

    if not isinstance(
        result,
        list,
    ):
        raise APIClientError(
            "Invalid companies response."
        )

    return result


def get_screener(
    min_roe: float | None = None,
    max_de: float | None = None,
    min_fcf: float | None = None,
    sector: str | None = None,
    min_rev_cagr_5yr: float | None = None,
    min_pat_cagr_5yr: float | None = None,
    max_pe: float | None = None,
) -> list[dict]:
    """Return ranked screener results from FastAPI."""

    result = api_get(
        "/screener",
        {
            "min_roe": min_roe,
            "max_de": max_de,
            "min_fcf": min_fcf,
            "sector": sector,
            "min_rev_cagr_5yr":
                min_rev_cagr_5yr,
            "min_pat_cagr_5yr":
                min_pat_cagr_5yr,
            "max_pe": max_pe,
        },
    )

    if not isinstance(
        result,
        list,
    ):
        raise APIClientError(
            "Invalid screener response."
        )

    return result