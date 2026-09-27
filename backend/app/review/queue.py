"""Review Queue and Versioned Decision Store — Layer 7.

Manages:
  - The officer review queue (prioritized by severity)
  - Versioned decision records (approve/reject/modify)
  - Evidence package generation
  - Audit trail for every decision
"""
from __future__ import annotations
import uuid
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.core.evidence_envelope import build_evidence_payload, sign_evidence, verify_envelope
from app.core.signing import get_signing_key, get_registry
from app.core.hashing import sha256_canonical
from app.models.domain import DecisionState, ConflictSeverity
from app.models.database import DBProposal, DBConflict, DBCanonicalParcel, DBAuditEvent
from app.harmonization.proposer import ProposalResult
from app.topology.ripple_check import RippleCheckResult


# Priority scoring for review queue
SEVERITY_PRIORITY = {
    ConflictSeverity.CRITICAL: 100,
    ConflictSeverity.HIGH: 70,
    ConflictSeverity.MEDIUM: 40,
    ConflictSeverity.LOW: 10,
}


@dataclass
class ReviewQueueItem:
    item_id: str
    proposal_id: str
    parcel_id: str
    case_id: str
    priority: int
    reason: str
    conflict_types: list[str] = field(default_factory=list)
    conflict_count: int = 0
    ripple_issues: int = 0
    match_confidence: float = 0.0
    created_at: str = ""
    status: str = "PENDING"
    assigned_to: Optional[str] = None


@dataclass
class DecisionRecord:
    decision_id: str
    proposal_id: str
    parcel_id: str
    case_id: str
    decision: DecisionState
    decision_reason: str
    actor: str
    timestamp: str
    version: int
    evidence_envelope: Optional[dict] = None
    evidence_hash: Optional[str] = None


def compute_review_priority(
    proposal: ProposalResult,
    ripple: Optional[RippleCheckResult] = None,
    conflicts: list = None,
) -> int:
    """Compute priority score for review queue (higher = more urgent)."""
    priority = 0
    # Confidence penalty
    priority += int((1.0 - proposal.match_confidence) * 50)
    # Unresolved conflicts
    priority += len(proposal.conflicts_unresolved) * 15
    # Max severity of unresolved conflicts
    if conflicts:
        for c in conflicts:
            if c.conflict_id in proposal.conflicts_unresolved:
                priority += SEVERITY_PRIORITY.get(c.severity, 0)
    # Ripple issues
    if ripple:
        priority += ripple.critical_issues * 30
        priority += (ripple.total_issues - ripple.critical_issues) * 10
    # Boundary offset
    if proposal.max_boundary_offset_m > 5:
        priority += 30
    elif proposal.max_boundary_offset_m > 2:
        priority += 15
    return priority


class ReviewQueue:
    """In-memory review queue with DB persistence."""

    def __init__(self, db: Optional[Session] = None):
        self._items: dict[str, ReviewQueueItem] = {}
        self._db = db

    def enqueue(
        self,
        proposal: ProposalResult,
        case_id: str,
        ripple: Optional[RippleCheckResult] = None,
        conflicts: list = None,
    ) -> ReviewQueueItem:
        """Add a proposal to the review queue."""
        item_id = f"REVIEW-{uuid.uuid4().hex[:8].upper()}"
        priority = compute_review_priority(proposal, ripple, conflicts)

        conflict_types = []
        if conflicts:
            conflict_types = list(set(
                c.conflict_type.value for c in conflicts
                if c.conflict_id in proposal.conflicts_unresolved
            ))

        item = ReviewQueueItem(
            item_id=item_id,
            proposal_id=proposal.proposal_id,
            parcel_id=proposal.parcel_id,
            case_id=case_id,
            priority=priority,
            reason=proposal.decision_reason,
            conflict_types=conflict_types,
            conflict_count=len(proposal.conflicts_unresolved),
            ripple_issues=ripple.total_issues if ripple else 0,
            match_confidence=proposal.match_confidence,
            created_at=datetime.now(timezone.utc).isoformat(),
            status="PENDING",
        )
        self._items[item_id] = item
        return item

    def get_queue(self, case_id: Optional[str] = None) -> list[ReviewQueueItem]:
        """Return queue sorted by priority (high first)."""
        items = [i for i in self._items.values() if i.status == "PENDING"]
        if case_id:
            items = [i for i in items if i.case_id == case_id]
        return sorted(items, key=lambda x: x.priority, reverse=True)

    def get_item(self, item_id: str) -> Optional[ReviewQueueItem]:
        return self._items.get(item_id)

    def mark_processed(self, item_id: str, status: str = "PROCESSED") -> None:
        if item_id in self._items:
            self._items[item_id].status = status


class DecisionStore:
    """Stores and retrieves versioned harmonization decisions with signed evidence."""

    def __init__(self, data_dir: Path):
        self._dir = data_dir / "decisions"
        self._dir.mkdir(parents=True, exist_ok=True)

    def record_decision(
        self,
        proposal: ProposalResult,
        case_id: str,
        decision: DecisionState,
        reason: str,
        actor: str,
        ripple: Optional[RippleCheckResult] = None,
        db: Optional[Session] = None,
    ) -> DecisionRecord:
        """Record a decision, sign the evidence package, persist to disk + DB."""
        decision_id = f"DEC-{uuid.uuid4().hex[:8].upper()}"
        timestamp = datetime.now(timezone.utc).isoformat()

        # Build evidence payload
        payload = build_evidence_payload(
            comparison_id=decision_id,
            case_id=case_id,
            parcel_ids=[proposal.parcel_id],
            source_record_ids=list(proposal.source_weights.keys()),
            conflict_types=[],
            match_result=proposal.confidence_components,
            harmonization_proposal={
                "proposal_id": proposal.proposal_id,
                "max_boundary_offset_m": proposal.max_boundary_offset_m,
                "area_change_pct": proposal.area_change_pct,
                "change_summary": proposal.change_summary,
            },
            validation_result=ripple.to_dict() if ripple else {},
            provenance_result={
                "independent_lineages": proposal.independent_lineages,
            },
            decision=decision.value,
            decision_reason=reason,
            actor=actor,
        )

        # Sign
        sk = get_signing_key()
        envelope = sign_evidence(payload, sk)

        # Persist to disk
        filepath = self._dir / f"{decision_id}.json"
        filepath.write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8")

        # Persist to DB
        if db:
            db_prop = db.query(DBProposal).filter(
                DBProposal.proposal_id == proposal.proposal_id
            ).first()
            if db_prop:
                db_prop.decision = decision.value
                db_prop.decision_reason = reason
                db_prop.decision_actor = actor
                db_prop.decision_timestamp = datetime.now(timezone.utc)
                db_prop.evidence_hash = envelope.get("evidence_hash")
                db_prop.signature = envelope.get("signature")
                db.commit()

            # Audit event
            event_content = {
                "decision_id": decision_id,
                "proposal_id": proposal.proposal_id,
                "parcel_id": proposal.parcel_id,
                "decision": decision.value,
                "reason": reason,
                "actor": actor,
                "evidence_hash": envelope.get("evidence_hash"),
            }
            audit_event = DBAuditEvent(
                event_id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
                timestamp_utc=timestamp,
                case_id=case_id,
                event_type=f"DECISION_{decision.value}",
                actor=actor,
                details=event_content,
                event_hash=sha256_canonical(event_content).hex_digest,
            )
            db.add(audit_event)
            db.commit()

        return DecisionRecord(
            decision_id=decision_id,
            proposal_id=proposal.proposal_id,
            parcel_id=proposal.parcel_id,
            case_id=case_id,
            decision=decision,
            decision_reason=reason,
            actor=actor,
            timestamp=timestamp,
            version=proposal.version,
            evidence_envelope=envelope,
            evidence_hash=envelope.get("evidence_hash"),
        )

    def load_decision(self, decision_id: str) -> Optional[dict]:
        """Load a decision envelope from disk."""
        filepath = self._dir / f"{decision_id}.json"
        if not filepath.exists():
            return None
        return json.loads(filepath.read_text(encoding="utf-8"))

    def verify_decision(self, decision_id: str) -> tuple[bool, str]:
        """Independently verify a stored decision."""
        envelope = self.load_decision(decision_id)
        if envelope is None:
            return False, f"Decision {decision_id} not found"
        return verify_envelope(envelope, get_registry())
