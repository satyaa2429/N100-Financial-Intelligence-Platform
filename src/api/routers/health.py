"""API health-check route."""

from __future__ import annotations

import sqlite3
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.api.database import (
    DB_PATH,
    table_row_counts,
)


router = APIRouter(
    prefix="/api/v1",
    tags=["Health"],
)


START_TIME = (
    time.monotonic()
)


@router.get(
    "/health",
    summary="Server health check",
)
def health():
    """Return API and database health."""

    try:

        row_counts = (
            table_row_counts()
        )

        return {
            "status": "healthy",
            "database":
                str(DB_PATH),
            "db_row_counts":
                row_counts,
            "uptime_seconds":
                round(
                    time.monotonic()
                    - START_TIME,
                    2,
                ),
            "version":
                "1.0.0",
        }

    except sqlite3.Error as exc:

        return JSONResponse(
            status_code=503,
            content={
                "status":
                    "unhealthy",
                "error":
                    str(exc),
                "uptime_seconds":
                    round(
                        time.monotonic()
                        - START_TIME,
                        2,
                    ),
                "version":
                    "1.0.0",
            },
        )