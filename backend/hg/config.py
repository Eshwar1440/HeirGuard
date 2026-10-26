"""Environment settings and named hypothetical defaults.

Every tunable number that does not come from a cited source lives here with a
``hypothetical`` label, so code, UI and README can point at one place.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/hg/config.py -> repo root. The Docker image mirrors this layout.
REPO_ROOT = Path(__file__).resolve().parents[2]

# --- Named hypothetical defaults (not from any source; tunable) -------------

#: hypothetical, tunable. Extracted fields below this confidence need review.
CONFIDENCE_THRESHOLD: float = 0.85

#: hypothetical. Annual growth rate assumed for inherited balances.
DEFAULT_GROWTH_RATE: Decimal = Decimal("0.05")

#: hypothetical, tunable. RapidFuzz token_sort_ratio at or above this (and not
#: an exact match) links two names with POSSIBLY_SAME_AS.
NAME_MATCH_THRESHOLD: int = 90

DEFAULT_MODEL = "claude-sonnet-5-5"


class Settings(BaseSettings):
    """Values read from the environment (or a local ``.env``).

    Defaults are empty so imports and tests work without secrets. Code that
    needs a secret checks for it at the point of use.
    """

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = ""
    anthropic_model: str = DEFAULT_MODEL

    supabase_url: str = ""
    supabase_service_key: str = ""

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""

    database_url: str = ""
    web_origin: str = "http://localhost:5173"

    ai_log_dir: Path = REPO_ROOT / "ai_log"
    data_dir: Path = REPO_ROOT / "data"

    confidence_threshold: float = CONFIDENCE_THRESHOLD
    default_growth_rate: Decimal = DEFAULT_GROWTH_RATE
    name_match_threshold: int = NAME_MATCH_THRESHOLD


@lru_cache
def get_settings() -> Settings:
    return Settings()
