"""Unit tests for evidence signing and verification."""
import pytest
from app.core.signing import init_signing, get_signing_key, get_registry, SigningKey, TrustRegistry
from app.core.evidence_envelope import build_evidence_payload, sign_evidence, verify_envelope
from app.core.hashing import sha256_canonical


def make_payload():
    return build_evidence_payload(
        "BENCH-001", "CASE-TEST", ["P-001"], ["R-A", "R-B"],
        ["BOUNDARY_OFFSET"],
        {"geometry": 0.92, "identifier": 1.0, "overall": 0.94},
        {"proposal_id": "PROP-001", "max_boundary_offset_m": 1.42},
        {"safe_to_auto_approve": False, "total_issues": 1},
        {"independent_lineages": 3},
        "REVIEW_REQUIRED",
        "Boundary offset 1.42m",
    )


class TestSigningAndVerification:
    def test_sign_then_verify(self):
        payload = make_payload()
        key = get_signing_key()
        envelope = sign_evidence(payload, key)
        valid, reason = verify_envelope(envelope, get_registry())
        assert valid, reason

    def test_tamper_detected(self):
        payload = make_payload()
        key = get_signing_key()
        envelope = sign_evidence(payload, key)
        envelope["independent_lineages_in_result"] = 99  # tamper
        # Re-hash to bypass hash check, but signature will fail
        valid, reason = verify_envelope(envelope, get_registry())
        assert not valid

    def test_hash_mismatch_detected(self):
        payload = make_payload()
        key = get_signing_key()
        envelope = sign_evidence(payload, key)
        # Directly corrupt the hash
        envelope["evidence_hash"] = "00" * 32
        valid, reason = verify_envelope(envelope, get_registry())
        assert not valid
        assert "tampered" in reason.lower() or "mismatch" in reason.lower()

    def test_unknown_key_rejected(self):
        payload = make_payload()
        key = get_signing_key()
        envelope = sign_evidence(payload, key)
        envelope["signing"]["key_id"] = "FAKE-KEY-ID"
        valid, reason = verify_envelope(envelope, get_registry())
        assert not valid

    def test_missing_signature_rejected(self):
        payload = make_payload()
        key = get_signing_key()
        envelope = sign_evidence(payload, key)
        del envelope["signature"]
        valid, reason = verify_envelope(envelope, get_registry())
        assert not valid

    def test_canonical_hash_deterministic(self):
        obj = {"b": 2, "a": 1, "c": [3, 1, 2]}
        h1 = sha256_canonical(obj).hex_digest
        h2 = sha256_canonical(obj).hex_digest
        assert h1 == h2

    def test_key_registration_idempotent(self):
        """Registering the same key twice should not raise."""
        key = get_signing_key()
        reg = get_registry()
        # Should silently succeed (same key bytes)
        reg.register(key.key_id, key.public_bytes)
