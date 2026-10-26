-- HeritageGuard initial schema. All data stored here is hypothetical.
-- Only the backend (service role key) reads and writes these tables. RLS is
-- enabled with no policies, so anon/authenticated browser keys get nothing.
-- LangGraph checkpoint tables are created separately by PostgresSaver.setup().

create table if not exists public.cases (
    case_id     text primary key,
    status      text not null default 'intake',
    payload     jsonb not null default '{}'::jsonb,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

create table if not exists public.documents (
    id          bigint generated always as identity primary key,
    case_id     text not null references public.cases (case_id) on delete cascade,
    payload     jsonb not null,
    created_at  timestamptz not null default now()
);

create table if not exists public.guide_text (
    id          bigint generated always as identity primary key,
    case_id     text not null references public.cases (case_id) on delete cascade,
    payload     jsonb not null,
    created_at  timestamptz not null default now()
);

create table if not exists public.scenarios (
    id          bigint generated always as identity primary key,
    case_id     text not null references public.cases (case_id) on delete cascade,
    payload     jsonb not null,
    created_at  timestamptz not null default now()
);

create table if not exists public.audit_entries (
    id          bigint generated always as identity primary key,
    case_id     text not null references public.cases (case_id) on delete cascade,
    payload     jsonb not null,
    created_at  timestamptz not null default now()
);

create index if not exists documents_case_idx     on public.documents (case_id, created_at);
create index if not exists guide_text_case_idx    on public.guide_text (case_id, created_at);
create index if not exists scenarios_case_idx     on public.scenarios (case_id, created_at);
create index if not exists audit_entries_case_idx on public.audit_entries (case_id, created_at);

alter table public.cases         enable row level security;
alter table public.documents     enable row level security;
alter table public.guide_text    enable row level security;
alter table public.scenarios     enable row level security;
alter table public.audit_entries enable row level security;

-- Private bucket for uploaded and sample packet files.
insert into storage.buckets (id, name, public)
values ('packets', 'packets', false)
on conflict (id) do nothing;
