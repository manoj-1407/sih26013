"""Ed25519 signing for GeoSamanvay evidence envelopes.

Keys are persisted to disk (PEM/PKCS8) so signatures survive restarts.
The trust registry maps key_id → public key bytes for independent verification.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

from app.core.hashing import canonical_json


EXAMINER_KEY_ID = "KEY-GS-EXAMINER-26013-v1"


class SigningKey:
    def __init__(self, key_id: str, private_key: Ed25519PrivateKey):
        self.key_id = key_id
        self._private = private_key
        self.public_bytes = private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )

    @classmethod
    def generate(cls, key_id: str) -> "SigningKey":
        return cls(key_id, Ed25519PrivateKey.generate())

    @classmethod
    def load(cls, key_id: str, key_bytes: bytes) -> "SigningKey":
        """Load from PEM (new) or raw bytes (legacy). Auto-detects format."""
        if b"BEGIN" in key_bytes:
            private_key = serialization.load_pem_private_key(key_bytes, password=None)
        else:
            private_key = Ed25519PrivateKey.from_private_bytes(key_bytes)
        return cls(key_id, private_key)

    def private_pem_bytes(self) -> bytes:
        return self._private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )

    def sign(self, payload: dict) -> str:
        """Sign canonical JSON. Returns hex signature."""
        return self.sign_bytes(canonical_json(payload))

    def sign_bytes(self, raw: bytes) -> str:
        return self._private.sign(raw).hex()


class TrustRegistry:
    """Immutable after registration: key_id → public key bytes."""

    def __init__(self):
        self._keys: dict[str, bytes] = {}

    def register(self, key_id: str, public_bytes: bytes) -> None:
        if key_id in self._keys:
            # Allow re-registration with same key (idempotent restart)
            if self._keys[key_id] != public_bytes:
                raise ValueError(f"Key {key_id!r} already registered with different public key")
            return
        self._keys[key_id] = public_bytes

    def verify(self, key_id: str, payload: dict, signature_hex: str) -> bool:
        if key_id not in self._keys:
            raise KeyError(f"Key {key_id!r} not in trust registry")
        raw = canonical_json(payload)
        try:
            pub = Ed25519PublicKey.from_public_bytes(self._keys[key_id])
            pub.verify(bytes.fromhex(signature_hex), raw)
            return True
        except (InvalidSignature, ValueError):
            return False

    def has_key(self, key_id: str) -> bool:
        return key_id in self._keys


# Module singletons
_registry = TrustRegistry()
_signing_key: SigningKey | None = None


def _default_data_dir() -> Path:
    env_dir = os.environ.get("GS_DATA_DIR")
    if env_dir:
        return Path(env_dir)
    return Path(__file__).resolve().parents[3] / "data"


def init_signing(data_dir: Path | None = None) -> None:
    """Initialize or reload signing key from disk. Idempotent."""
    global _signing_key
    if _signing_key is not None:
        return  # Already initialized

    if data_dir is None:
        data_dir = _default_data_dir()

    key_dir = data_dir / "keys"
    key_dir.mkdir(parents=True, exist_ok=True)
    key_path = key_dir / "gs_examiner.priv"
    reg_path = key_dir / "trust_registry.json"

    if key_path.exists():
        raw = key_path.read_bytes()
        _signing_key = SigningKey.load(EXAMINER_KEY_ID, raw)
    else:
        _signing_key = SigningKey.generate(EXAMINER_KEY_ID)
        key_path.write_bytes(_signing_key.private_pem_bytes())
        try:
            key_path.chmod(0o600)
        except OSError:
            pass

    _registry.register(EXAMINER_KEY_ID, _signing_key.public_bytes)
    reg_path.write_text(
        json.dumps({EXAMINER_KEY_ID: _signing_key.public_bytes.hex()}, indent=2),
        encoding="utf-8",
    )


def _ensure_initialized() -> None:
    global _signing_key
    if _signing_key is None:
        init_signing()


def get_signing_key() -> SigningKey:
    _ensure_initialized()
    return _signing_key


def get_registry() -> TrustRegistry:
    _ensure_initialized()
    return _registry
