"""Which fitment evidence counts, per runtime mode (T-022; ARCHITECTURE §3 and §5 ``fitment``).

Rules, enforced here and mirrored by the ``ck_fitment_verified_evidence`` CHECK in the DB:

- Only ``oem_catalog``, ``manufacturer_doc`` and ``owner_confirmed`` can verify, and only with a
  non-empty reference and a verification time.
- Visual similarity, customer statements, LLM output, listing titles and "same body code" are
  never evidence, whatever status the record claims.
- ``synthetic_fixture`` counts only in ``test`` mode and only on synthetic records. In
  ``development`` it is ignored (the part stays ``needs_verification``). In ``production`` any
  synthetic record or synthetic evidence raises ``SyntheticDataRejected``: it must never reach
  a customer as a real verification.
- A synthetic record claiming a real evidence kind is not accepted (made-up data must not
  pretend to be an owner confirmation or a catalog lookup).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.catalog.runtime import RuntimeMode, SyntheticDataRejected, current_runtime_mode
from app.catalog.types import (
    NON_EVIDENCE_KINDS,
    QUALIFYING_EVIDENCE_KINDS,
    EvidenceKind,
    FitmentRecord,
    Provenance,
)


class EvidenceRejection(StrEnum):
    MISSING = "evidence_missing"
    KIND_NOT_EVIDENCE = "evidence_kind_not_evidence"
    REF_MISSING = "evidence_ref_missing"
    VERIFIED_AT_MISSING = "evidence_verified_at_missing"
    SYNTHETIC_NOT_ACCEPTED = "synthetic_evidence_not_accepted"
    SYNTHETIC_ON_REAL_RECORD = "synthetic_evidence_on_real_record"
    SYNTHETIC_RECORD_CLAIMS_REAL_KIND = "synthetic_record_claims_real_evidence"


@dataclass(frozen=True)
class EvidenceVerdict:
    accepted: bool
    rejection: EvidenceRejection | None = None
    synthetic: bool = False


@dataclass(frozen=True)
class EvidencePolicy:
    mode: RuntimeMode

    @classmethod
    def from_env(cls) -> EvidencePolicy:
        return cls(current_runtime_mode())

    def check_origin(self, provenance: Provenance, what: str) -> None:
        """Raise in production when a synthetic row reaches the catalog logic."""
        if self.mode is RuntimeMode.PRODUCTION and provenance.synthetic:
            raise SyntheticDataRejected(f"synthetic {what} refused in production mode")

    def assess(self, record: FitmentRecord) -> EvidenceVerdict:
        """Decide whether ``record``'s evidence may support a definite (verified or
        incompatible) answer. The record's own status is not considered here."""
        self.check_origin(record.provenance, f"fitment record {record.record_id}")
        evidence = record.evidence
        if evidence is None:
            return EvidenceVerdict(False, EvidenceRejection.MISSING)
        kind = evidence.kind
        if kind is EvidenceKind.SYNTHETIC_FIXTURE and self.mode is RuntimeMode.PRODUCTION:
            raise SyntheticDataRejected(
                f"synthetic evidence on {record.record_id} refused in production mode"
            )
        if kind in NON_EVIDENCE_KINDS:
            return EvidenceVerdict(False, EvidenceRejection.KIND_NOT_EVIDENCE)
        if not (evidence.ref or "").strip():
            return EvidenceVerdict(False, EvidenceRejection.REF_MISSING)
        if evidence.verified_at is None:
            return EvidenceVerdict(False, EvidenceRejection.VERIFIED_AT_MISSING)
        if kind is EvidenceKind.SYNTHETIC_FIXTURE:
            if not record.provenance.synthetic:
                return EvidenceVerdict(False, EvidenceRejection.SYNTHETIC_ON_REAL_RECORD)
            if self.mode is RuntimeMode.TEST:
                return EvidenceVerdict(True, synthetic=True)
            return EvidenceVerdict(False, EvidenceRejection.SYNTHETIC_NOT_ACCEPTED, synthetic=True)
        if kind in QUALIFYING_EVIDENCE_KINDS:
            if record.provenance.synthetic:
                return EvidenceVerdict(False, EvidenceRejection.SYNTHETIC_RECORD_CLAIMS_REAL_KIND)
            return EvidenceVerdict(True)
        # A new enum member that nobody classified: fail closed.
        return EvidenceVerdict(False, EvidenceRejection.KIND_NOT_EVIDENCE)
