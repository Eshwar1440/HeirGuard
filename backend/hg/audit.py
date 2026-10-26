"""M8 audit trail. Every flow node appends AuditEntry records.

The entries live in the flow state (so they survive with the LangGraph
checkpoint) and are mirrored to Supabase through hg.store when it is configured.
A mirror failure is logged, never raised: the audit in the checkpoint stays the
source of truth.
"""

from __future__ import annotations

import logging
from typing import Iterable

from hg import store
from hg.config import get_settings
from hg.schemas import AuditEntry, CaseState

log = logging.getLogger(__name__)


def entry(case_id: str, node: str, action: str, summary: str) -> AuditEntry:
    return AuditEntry(case_id=case_id, node=node, action=action, summary=summary)


def supabase_enabled() -> bool:
    settings = get_settings()
    return bool(settings.supabase_url and settings.supabase_service_key)


def mirror(case: CaseState, entries: Iterable[AuditEntry]) -> None:
    """Save the case row and new audit entries to Supabase, if configured."""
    entries = list(entries)
    if not supabase_enabled():
        return
    try:
        store.upsert_case(case)
        for e in entries:
            store.save_audit_entry(e)
    except Exception as exc:  # the checkpoint keeps the audit; report and carry on
        log.warning("audit mirror to Supabase failed for %s: %s", case.case_id, exc)
