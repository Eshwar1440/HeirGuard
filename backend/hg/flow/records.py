"""Find the account on file for documents uploaded without a case.

The death certificate's decedent name and date of death are matched against the records
on file (the synthetic packets' truth files stand in for the custodian's records). A match
brings the decedent, accounts and beneficiary designations into the case.
"""

from __future__ import annotations

import json
from typing import Optional

from hg.config import get_settings
from hg.data_gen import load_truth
from hg.graph.resolve import field_value, normalize_name
from hg.schemas import CaseState


def match_records(case: CaseState) -> Optional[tuple[str, CaseState]]:
    """(record id, case with records attached), or None when no certificate matches one record."""
    certs = [d for d in case.documents if d.doc_type == "death_certificate"]
    keys = {(normalize_name(field_value(d, "decedent_name") or ""), field_value(d, "date_of_death")) for d in certs}
    if not certs:
        return None
    packets = get_settings().data_dir / "packets"
    found = []
    for entry in json.loads((packets / "index.json").read_text(encoding="utf-8")):
        truth = load_truth(packets / entry["packet_id"])
        key = (normalize_name(truth.decedent.name), truth.decedent.date_of_death.isoformat())
        if key in keys:
            found.append((entry["packet_id"], truth))
    # packet_01_flawed and packet_01_fixed share one family: either record works, so take the first.
    if not found:
        return None
    record_id, truth = found[0]
    return record_id, case.model_copy(update={
        "decedent": truth.decedent, "accounts": truth.accounts, "beneficiaries": truth.beneficiaries,
    })
