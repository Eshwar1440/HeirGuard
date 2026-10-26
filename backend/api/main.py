"""FastAPI entry point. Routes are added in M8."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hg.config import get_settings

DISCLAIMER = "Concept prototype. Not affiliated with Charles Schwab. All data is hypothetical."

app = FastAPI(title="HeritageGuard API", description=DISCLAIMER, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().web_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "notice": DISCLAIMER}
