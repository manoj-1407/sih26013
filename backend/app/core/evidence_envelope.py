"""Evidence envelope: sign, store, and independently verify harmonization decisions.

Every harmonization proposal produces a signed evidence package.
Verification is stateless: given the envelope + trust registry → valid/invalid.
The verifier holds no write access.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.hashing import sha256_canonical, sha256_bytes, canonical_json
from app.core.signing import SigningKey, TrustRegistry, get_signing_key, get_registry


def build_evidence_payload(
    comparison_id: str,
    case_id: str,
    parcel_ids: list[str],
    source_record_ids: list[str],
    conflict_types: list[str],
    match_result: dict,
    harmonization_proposal: dict,
    validation_result: dict,
    provenance_result: dict,
    decision: str,
    decision_reason: str,
    actor: str = "system",
) -> dict:
    """Assemble canonical evidence dict for signing."""
    return {
        "schema_version": "gs-evidence-v1",
        "comparison_id": comparison_id,
        "case_id": case_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "parcel_ids": sorted(parcel_ids),
        "source_record_ids": sorted(source_record_ids),
        "conflict_types": conflict_types,
        "match_result": match_result,
        "harmonization_proposal": harmonization_proposal,
        "validation_result": validation_result,
        "provenance_result": provenance_result,
        "decision": decision,
        "decision_reason": decision_reason,
        "actor": actor,
    }


def sign_evidence(payload: dict, signing_key: SigningKey | None = None) -> dict:
    """Sign evidence payload. Returns full envelope with hash + signature."""
    if signing_key is None:
        signing_key = get_signing_key()

    raw = canonical_json(payload)
    evidence_hash = sha256_bytes(raw).hex_digest
    sig_hex = signing_key.sign_bytes(raw)

    return {
        **payload,
        "evidence_hash": evidence_hash,
        "signature": sig_hex,
        "signing": {
            "algorithm": "Ed25519",
            "key_id": signing_key.key_id,
        },
    }


def verify_envelope(envelope: dict, registry: TrustRegistry | None = None) -> tuple[bool, str]:
    """
    Stateless verification of a signed evidence envelope.
    Returns (is_valid, explanation).
    """
    if registry is None:
        registry = get_registry()

    key_id = envelope.get("signing", {}).get("key_id")
    sig_hex = envelope.get("signature")
    stored_hash = envelope.get("evidence_hash")

    if not key_id:
        return False, "missing signing.key_id"
    if not sig_hex:
        return False, "missing signature"
    if not stored_hash:
        return False, "missing evidence_hash"

    # Reconstruct payload (strip envelope-level fields)
    payload = {k: v for k, v in envelope.items()
               if k not in ("evidence_hash", "signature", "signing")}

    # Step 1: content hash
    computed = sha256_canonical(payload).hex_digest
    if computed != stored_hash:
        return False, "evidence_hash mismatch — payload has been tampered with"

    # Step 2: Ed25519 signature
    try:
        valid = registry.verify(key_id, payload, sig_hex)
    except KeyError:
        return False, f"key {key_id!r} not in trust registry"

    if not valid:
        return False, "Ed25519 signature verification failed"

    return True, f"Verified using trusted key {key_id}"
