"""Evidence Package Exporter — Layer 8.

Generates a portable, self-contained evidence package for each
harmonization decision:

  parcel_{id}/
    ├── source_manifest.json      (source records + hashes)
    ├── normalized_features.geojson
    ├── proposal.geojson
    ├── conflicts.json
    ├── confidence.json
    ├── provenance.json
    ├── validation.json
    ├── decision.json
    ├── audit.jsonl
    └── manifest.sha256

Output formats: GeoJSON bundle (ZIP) or GeoPackage (when fiona available).
"""
from __future__ import annotations
import json
import zipfile
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.hashing import sha256_canonical, sha256_bytes
from app.harmonization.proposer import ProposalResult
from app.topology.ripple_check import RippleCheckResult
from app.review.queue import DecisionRecord
from app.ingestion.ingestor import IngestedRecord
from app.conflicts.detector import DetectedConflict
from app.models.domain import DecisionState


def _geojson_feature(geometry: Optional[dict], properties: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": properties,
    }


def _feature_collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


def export_evidence_package(
    parcel_id: str,
    case_id: str,
    records: list[IngestedRecord],
    proposal: ProposalResult,
    conflicts: list[DetectedConflict],
    ripple: Optional[RippleCheckResult],
    decision: Optional[DecisionRecord],
    audit_events: Optional[list[dict]] = None,
) -> bytes:
    """
    Generate a ZIP archive containing the full evidence package.
    Returns raw bytes of the ZIP file.
    """
    buf = io.BytesIO()
    prefix = f"parcel_{parcel_id}"

    manifest_entries: dict[str, str] = {}

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:

        # 1. Source manifest
        source_manifest = {
            "parcel_id": parcel_id,
            "case_id": case_id,
            "exported_at_utc": datetime.now(timezone.utc).isoformat(),
            "sources": [
                {
                    "record_id": r.record_id,
                    "source_type": r.source_type.value,
                    "dataset_id": r.dataset_id,
                    "capture_timestamp": r.capture_timestamp,
                    "content_hash": r.content_hash,
                    "area_sqm": r.area_sqm,
                    "attributes_canonical": r.attributes_canonical,
                }
                for r in records
            ],
        }
        sm_bytes = json.dumps(source_manifest, indent=2, ensure_ascii=False).encode("utf-8")
        manifest_entries["source_manifest.json"] = sha256_bytes(sm_bytes).hex_digest
        zf.writestr(f"{prefix}/source_manifest.json", sm_bytes)

        # 2. Normalized features GeoJSON
        features = [
            _geojson_feature(
                r.geometry_geojson,
                {
                    "record_id": r.record_id,
                    "source_type": r.source_type.value,
                    "area_sqm": r.area_sqm,
                    "capture_timestamp": r.capture_timestamp,
                    **{k: v for k, v in r.attributes_canonical.items() if not k.startswith("_")},
                },
            )
            for r in records
        ]
        norm_fc = _feature_collection(features)
        norm_bytes = json.dumps(norm_fc, indent=2, ensure_ascii=False).encode("utf-8")
        manifest_entries["normalized_features.geojson"] = sha256_bytes(norm_bytes).hex_digest
        zf.writestr(f"{prefix}/normalized_features.geojson", norm_bytes)

        # 3. Proposal GeoJSON
        if proposal.proposed_geometry:
            prop_feature = _geojson_feature(
                proposal.proposed_geometry,
                {
                    "proposal_id": proposal.proposal_id,
                    "parcel_id": parcel_id,
                    "version": proposal.version,
                    "decision": proposal.decision.value,
                    **{k: str(v) for k, v in proposal.proposed_attributes.items() if not k.startswith("_")},
                },
            )
            prop_fc = _feature_collection([prop_feature] + features)
            prop_bytes = json.dumps(prop_fc, indent=2, ensure_ascii=False).encode("utf-8")
        else:
            prop_bytes = json.dumps({"error": "no proposed geometry"}).encode("utf-8")
        manifest_entries["proposal.geojson"] = sha256_bytes(prop_bytes).hex_digest
        zf.writestr(f"{prefix}/proposal.geojson", prop_bytes)

        # 4. Conflicts
        conflicts_data = {
            "parcel_id": parcel_id,
            "total": len(conflicts),
            "by_severity": {
                "CRITICAL": sum(1 for c in conflicts if c.severity.value == "CRITICAL"),
                "HIGH": sum(1 for c in conflicts if c.severity.value == "HIGH"),
                "MEDIUM": sum(1 for c in conflicts if c.severity.value == "MEDIUM"),
                "LOW": sum(1 for c in conflicts if c.severity.value == "LOW"),
            },
            "conflicts": [
                {
                    "conflict_id": c.conflict_id,
                    "type": c.conflict_type.value,
                    "severity": c.severity.value,
                    "record_ids": c.record_ids,
                    "measure": c.measure,
                    "measure_unit": c.measure_unit,
                    "description": c.description,
                    "auto_resolvable": c.auto_resolvable,
                    "evidence": c.evidence,
                }
                for c in conflicts
            ],
        }
        conf_bytes = json.dumps(conflicts_data, indent=2, ensure_ascii=False).encode("utf-8")
        manifest_entries["conflicts.json"] = sha256_bytes(conf_bytes).hex_digest
        zf.writestr(f"{prefix}/conflicts.json", conf_bytes)

        # 5. Confidence
        confidence_data = {
            "parcel_id": parcel_id,
            "match_confidence": proposal.match_confidence,
            "independent_lineages": proposal.independent_lineages,
            "source_weights": proposal.source_weights,
            "confidence_components": proposal.confidence_components,
            "can_auto_approve": proposal.can_auto_approve,
            "auto_reject_reasons": proposal.auto_reject_reasons,
            "explanation": (
                "Confidence is a weighted composite of geometry, identifier, "
                "attribute, temporal, and provenance scores. "
                "It is NOT a probability — it is a matching signal."
            ),
        }
        conf2_bytes = json.dumps(confidence_data, indent=2, ensure_ascii=False).encode("utf-8")
        manifest_entries["confidence.json"] = sha256_bytes(conf2_bytes).hex_digest
        zf.writestr(f"{prefix}/confidence.json", conf2_bytes)

        # 6. Validation / Ripple
        ripple_data = ripple.to_dict() if ripple else {"status": "not_checked"}
        ripple_bytes = json.dumps(ripple_data, indent=2, ensure_ascii=False).encode("utf-8")
        manifest_entries["validation.json"] = sha256_bytes(ripple_bytes).hex_digest
        zf.writestr(f"{prefix}/validation.json", ripple_bytes)

        # 7. Decision
        decision_data = {
            "proposal_id": proposal.proposal_id,
            "parcel_id": parcel_id,
            "decision": proposal.decision.value if not decision else decision.decision.value,
            "reason": proposal.decision_reason if not decision else decision.decision_reason,
            "actor": "system" if not decision else decision.actor,
            "timestamp": datetime.now(timezone.utc).isoformat() if not decision else decision.timestamp,
            "version": proposal.version,
            "change_summary": proposal.change_summary,
            "evidence_hash": decision.evidence_hash if decision else None,
        }
        dec_bytes = json.dumps(decision_data, indent=2, ensure_ascii=False).encode("utf-8")
        manifest_entries["decision.json"] = sha256_bytes(dec_bytes).hex_digest
        zf.writestr(f"{prefix}/decision.json", dec_bytes)

        # 8. Audit trail
        if audit_events:
            audit_lines = "\n".join(
                json.dumps(e, ensure_ascii=False) for e in audit_events
            )
            audit_bytes = audit_lines.encode("utf-8")
        else:
            audit_bytes = b""
        manifest_entries["audit.jsonl"] = sha256_bytes(audit_bytes).hex_digest
        zf.writestr(f"{prefix}/audit.jsonl", audit_bytes)

        # 9. Manifest with SHA-256 checksums
        manifest_content = "# GeoSamanvay Evidence Package Manifest\n"
        manifest_content += f"# Parcel: {parcel_id}\n"
        manifest_content += f"# Case: {case_id}\n"
        manifest_content += f"# Generated: {datetime.now(timezone.utc).isoformat()}\n\n"
        for filename, filehash in manifest_entries.items():
            manifest_content += f"{filehash}  {filename}\n"
        zf.writestr(f"{prefix}/manifest.sha256", manifest_content.encode("utf-8"))

    return buf.getvalue()
