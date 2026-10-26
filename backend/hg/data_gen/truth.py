"""The truth.json written next to each generated packet."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from hg.schemas import Account, Beneficiary, CaseState, Decedent, Document

# Stable rule ids from M3 that a packet can have planted.
RuleId = Literal[
    "shares_total_100",
    "name_match",
    "dod_consistent",
    "required_docs_present",
    "certified_copy",
]


class PlantedError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: RuleId
    note: str
    document_id: Optional[str] = None
    beneficiary_id: Optional[str] = None


class PacketTruth(BaseModel):
    """Ground truth for one packet. Everything in it is hypothetical.

    ``documents`` hold each field exactly as printed (normalized per
    ``hg.data_gen.forms``), so they include planted errors: a perfect reader
    returns these values. ``decedent``, ``accounts`` and ``beneficiaries`` are
    the packet's facts as submitted; shares reflect what the applications say.
    """

    model_config = ConfigDict(extra="forbid")

    packet_id: str
    description: str
    notice: str = "SPECIMEN - HYPOTHETICAL DATA. No real person, account or record."
    decedent: Decedent
    accounts: list[Account]
    beneficiaries: list[Beneficiary]
    documents: list[Document]
    planted_errors: list[RuleId]
    planted_error_details: list[PlantedError]

    def case_state(self) -> CaseState:
        """A CaseState built straight from truth (no LLM), for checker tests."""
        return CaseState(
            case_id=self.packet_id,
            decedent=self.decedent,
            accounts=self.accounts,
            beneficiaries=self.beneficiaries,
            documents=self.documents,
        )

    def document(self, document_id: str) -> Document:
        return next(d for d in self.documents if d.id == document_id)

    def field(self, document_id: str, name: str) -> Optional[str]:
        return next(f.value for f in self.document(document_id).fields if f.name == name)
