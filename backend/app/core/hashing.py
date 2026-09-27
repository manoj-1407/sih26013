"""Canonical JSON hashing for evidence integrity.

Canonical form: UTF-8, keys sorted recursively, no extra whitespace.
This ensures the same logical payload always produces the same hash
regardless of insertion order — critical for evidence reproducibility.
"""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class HashResult:
    hex_digest: str
    algorithm: str = "sha256"


def canonical_json(obj: dict | list) -> bytes:
    """Serialize to canonical JSON bytes (sorted keys, no whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(raw: bytes) -> HashResult:
    """Hash raw bytes with SHA-256."""
    return HashResult(hex_digest=hashlib.sha256(raw).hexdigest())


def sha256_canonical(obj: dict | list) -> HashResult:
    """Hash canonical JSON of obj with SHA-256."""
    return sha256_bytes(canonical_json(obj))


def sha256_file(path: str) -> HashResult:
    """Hash a file's contents with SHA-256 (streaming, memory-safe)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return HashResult(hex_digest=h.hexdigest())
