"""Thin wrappers over Supabase (Postgres + Storage) and Neo4j.

Only the backend talks to these services. Clients are created lazily so that
importing this module never needs credentials.
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Iterable, Optional

from pydantic import BaseModel

from hg.config import get_settings
from hg.schemas import AuditEntry, CaseState, GuideText, Scenario

PACKETS_BUCKET = "packets"

# Table names from supabase/migrations/001_init.sql
CASES = "cases"
DOCUMENTS = "documents"
GUIDE_TEXT = "guide_text"
SCENARIOS = "scenarios"
AUDIT_ENTRIES = "audit_entries"


class StoreConfigError(RuntimeError):
    """A required connection setting is missing."""


# --- Supabase ----------------------------------------------------------------


@lru_cache
def get_supabase():
    from supabase import create_client

    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_key:
        raise StoreConfigError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    return create_client(settings.supabase_url, settings.supabase_service_key)


def upload_file(case_id: str, filename: str, data: bytes, content_type: str = "application/pdf") -> str:
    """Store a file in the private ``packets`` bucket. Returns ``packets/<case_id>/<filename>``."""
    path = f"{case_id}/{filename}"
    get_supabase().storage.from_(PACKETS_BUCKET).upload(
        path, data, {"content-type": content_type, "upsert": "true"}
    )
    return f"{PACKETS_BUCKET}/{path}"


def download_file(file_ref: str) -> bytes:
    bucket, _, path = file_ref.partition("/")
    return get_supabase().storage.from_(bucket).download(path)


def upsert_case(case: CaseState) -> None:
    """Create or update the case row. Call before saving any child record."""
    get_supabase().table(CASES).upsert(
        {
            "case_id": case.case_id,
            "status": case.status,
            "payload": case.model_dump(mode="json"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ).execute()


def load_case(case_id: str) -> Optional[CaseState]:
    result = get_supabase().table(CASES).select("payload").eq("case_id", case_id).execute()
    return CaseState.model_validate(result.data[0]["payload"]) if result.data else None


def save_record(table: str, case_id: str, payload: BaseModel | dict) -> None:
    """Insert one child record. The case row must already exist (see ``upsert_case``)."""
    if isinstance(payload, BaseModel):
        payload = payload.model_dump(mode="json")
    get_supabase().table(table).insert({"case_id": case_id, "payload": payload}).execute()


def load_records(table: str, case_id: str) -> list[dict]:
    """Payloads for a case, oldest first."""
    result = (
        get_supabase()
        .table(table)
        .select("payload")
        .eq("case_id", case_id)
        .order("created_at")
        .execute()
    )
    return [row["payload"] for row in result.data]


def save_scenarios(case_id: str, scenarios: Iterable[Scenario]) -> None:
    for scenario in scenarios:
        save_record(SCENARIOS, case_id, scenario)


def load_scenarios(case_id: str) -> list[Scenario]:
    return [Scenario.model_validate(p) for p in load_records(SCENARIOS, case_id)]


def save_guide_text(case_id: str, guide: GuideText) -> None:
    save_record(GUIDE_TEXT, case_id, guide)


def load_guide_text(case_id: str) -> list[GuideText]:
    return [GuideText.model_validate(p) for p in load_records(GUIDE_TEXT, case_id)]


def save_audit_entry(entry: AuditEntry) -> None:
    save_record(AUDIT_ENTRIES, entry.case_id, entry)


def load_audit_entries(case_id: str) -> list[AuditEntry]:
    return [AuditEntry.model_validate(p) for p in load_records(AUDIT_ENTRIES, case_id)]


# --- Neo4j -------------------------------------------------------------------


@lru_cache
def get_driver():
    from neo4j import GraphDatabase

    settings = get_settings()
    if not settings.neo4j_password:
        raise StoreConfigError("NEO4J_PASSWORD must be set")
    # Server notifications are off: they only warn that a relationship type
    # (e.g. POSSIBLY_SAME_AS) has no instances yet, which is normal here.
    return GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
        notifications_min_severity="OFF",
    )


def run(cypher: str, **params: Any) -> list[dict]:
    """Run one Cypher statement and return the records as dicts."""
    records, _, _ = get_driver().execute_query(cypher, parameters_=params)
    return [record.data() for record in records]


def close_driver() -> None:
    if get_driver.cache_info().currsize:
        get_driver().close()
        get_driver.cache_clear()
