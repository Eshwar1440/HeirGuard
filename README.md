# HeritageGuard

> **Concept prototype. Not affiliated with Charles Schwab. All data is hypothetical.**
> Every person, account, balance and document in this repo is synthetic. Any number not
> taken from a cited source is a named config value labeled `hypothetical`
> (see `backend/hg/config.py`).

HeritageGuard is a concept prototype for the UT Dallas JSOM "AI in Finance" case competition.
It helps an heir of a deceased brokerage client move from document upload to a prefilled
inherited-account application. An "under-the-hood" panel shows every AI step and check.

AI does exactly two jobs: **reading documents** (M2) and **writing plain English** (M5).
Numbers, routing and approvals are all deterministic code. Every LLM call goes through
`backend/hg/llm.py` and is logged to `ai_log/`.

## Repo layout

| Path | What |
|---|---|
| `backend/hg/schemas.py` | Shared Pydantic v2 contracts (money is always `Decimal`) |
| `backend/hg/config.py` | Env settings and named hypothetical defaults |
| `backend/hg/llm.py` | The only Anthropic client: SSN masking + JSONL call log |
| `backend/hg/store.py` | Supabase (Postgres + Storage) and Neo4j wrappers |
| `backend/api/` | FastAPI app |
| `web/` | React + TypeScript + Vite frontend |
| `supabase/migrations/` | SQL for tables and the private `packets` bucket |
| `data/packets/` | Generated synthetic estate packets |
| `ai_log/` | Raw LLM call logs (`*.jsonl`, git-ignored) and committed summaries (`*.md`) |

## Setup

Prerequisites: Python 3.11+, Node 20+, Docker. Nothing is installed globally.

```bash
cp .env.example .env   # then fill in values (never commit .env)
```

### Run the whole stack with Docker

```bash
docker compose up --build
```

- API: http://localhost:8000 (health check at `/health`, docs at `/docs`)
- Web: http://localhost:5173
- Neo4j browser: http://localhost:7474

Supabase (Postgres, Storage, the LangGraph checkpointer) stays hosted. Apply
`supabase/migrations/001_init.sql` in the Supabase SQL editor (or `supabase db push`).

### Host-side backend work (tests, scripts)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

Tests mock the Anthropic client and never call the API. The Neo4j test runs when a Neo4j is
reachable (`docker compose up neo4j`) and skips otherwise; CI always runs it against a
service container.

### Host-side web work

```bash
cd web
npm install
npm run dev     # Vite on 5173
npm test        # Vitest
```

## Environment variables

See [.env.example](.env.example). Backend: `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`,
`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`,
`DATABASE_URL`, `WEB_ORIGIN`. Web: `VITE_API_URL`. The browser never talks to Supabase or
Neo4j directly; only the backend holds keys.

## Hypothetical values

| Name | Value | Where |
|---|---|---|
| `CONFIDENCE_THRESHOLD` | 0.85 | `backend/hg/config.py` |
| `DEFAULT_GROWTH_RATE` | 0.05 | `backend/hg/config.py` |
| `NAME_MATCH_THRESHOLD` | 90 | `backend/hg/config.py` |
| Account balances | varies | synthetic packets, labeled in schema |

## LLM wrapper notes

`claude-sonnet-5-5` rejects forced tool use, so `extract_json` gets guaranteed-valid JSON
through structured outputs (`output_config.format` with a JSON schema). Requests opt into
the API's server-side refusal fallback; a refusal that still comes back raises
`LLMRefusalError` and is logged.
