"""LangGraph checkpointer: Postgres (Supabase) when DATABASE_URL is set.

Without DATABASE_URL the flow uses an in-memory saver, so local development and
tests run without Supabase. /health reports which one is active; in-memory cases
are lost when the process restarts.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from hg.config import get_settings

log = logging.getLogger(__name__)


@lru_cache
def get_checkpointer():
    url = get_settings().database_url
    if not url:
        from langgraph.checkpoint.memory import InMemorySaver

        log.warning("DATABASE_URL is not set: using an in-memory checkpointer (cases do not survive a restart)")
        return InMemorySaver()

    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    # prepare_threshold=0: Supabase's pooler does not support prepared statements.
    pool = ConnectionPool(
        url,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        max_size=5,
        open=True,
    )
    saver = PostgresSaver(pool)
    saver.setup()
    return saver


def checkpointer_kind() -> str:
    return "postgres" if get_settings().database_url else "memory"
