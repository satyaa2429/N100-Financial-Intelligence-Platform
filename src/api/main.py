"""FastAPI application for the Nifty 100 platform."""

from __future__ import annotations

from fastapi import FastAPI

from src.api.routers import (
    companies,
    health,
    peers,
    reports,
    screener,
    sectors,
)


app = FastAPI(
    title=(
        "Nifty 100 Financial "
        "Intelligence API"
    ),
    description=(
        "REST API for company profiles, "
        "financial statements, ratios, "
        "screening, sectors, peers, "
        "reports and portfolio analytics."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


app.include_router(
    companies.router
)

app.include_router(
    screener.router
)

app.include_router(
    sectors.router
)

app.include_router(
    peers.router
)

app.include_router(
    reports.router
)

app.include_router(
    health.router
)