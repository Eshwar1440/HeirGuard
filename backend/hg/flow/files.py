"""Where uploaded and sample files live.

A file reference names its store:

* ``sample:<packet_id>/<filename>``: a generated packet under data/packets/
* ``supabase:packets/<case_id>/<filename>``: Supabase Storage (when configured)
* ``local:<case_id>/<filename>``: data/uploads/ (local development without Supabase)
"""

from __future__ import annotations

import re
from pathlib import Path

from hg import store
from hg.audit import supabase_enabled
from hg.config import get_settings

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(filename: str) -> str:
    name = _SAFE.sub("_", Path(filename).name).strip("._")
    return name or "upload"


def _inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if root.resolve() not in path.parents:
        raise ValueError(f"file reference escapes its store: {relative!r}")
    return path


def _uploads_root() -> Path:
    return get_settings().data_dir / "uploads"


def sample_ref(packet_id: str, filename: str) -> str:
    return f"sample:{packet_id}/{filename}"


def save_upload(case_id: str, filename: str, data: bytes, content_type: str) -> str:
    name = safe_filename(filename)
    if supabase_enabled():
        return "supabase:" + store.upload_file(case_id, name, data, content_type)
    path = _inside(_uploads_root(), f"{case_id}/{name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return f"local:{case_id}/{name}"


def load(ref: str) -> bytes:
    kind, _, rest = ref.partition(":")
    data_dir = get_settings().data_dir
    if kind == "sample":
        return _inside(data_dir / "packets", rest).read_bytes()
    if kind == "local":
        return _inside(_uploads_root(), rest).read_bytes()
    if kind == "supabase":
        return store.download_file(rest)
    raise ValueError(f"unknown file reference {ref!r}")


def filename_of(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]
