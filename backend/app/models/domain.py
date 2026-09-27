"""GeoSamanvay canonical domain models.

These are the core data structures used throughout the system.
They are Pydantic models for serialization and SQLAlchemy models for persistence.
"""
from __future__ import annotations
from enum import Enum
from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────────────────────

class SourceType(str, Enum):
    CADASTRAL = "CADASTRAL"
    REVENUE_ROR = "REVENUE_ROR"
    MUNICIPAL_GIS = "MUNICIPAL_GIS"
    DRONE_ORI = "DRONE_ORI"
    GNSS_SURVEY = "GNSS_SURVEY"
    BUILDING_FOOTPRINT = "BUILDING_FOOTPRINT"
    UTILITY_NETWORK = "UTILITY_NETWORK"
    ADMINISTRATIVE = "ADMINISTRATIVE"
    ROAD_NETWORK = "ROAD_NETWORK"
    HISTORICAL = "HISTORICAL"
    UNKNOWN = "UNKNOWN"


class DataQualityLevel(str, Enum):
    HIGH = "HIGH"        # ≥90% complete, valid geometries, recent
    MEDIUM = "MEDIUM"    # 70-90%
    LOW = "LOW"          # <70%
    UNKNOWN = "UNKNOWN"


class ConflictType(str, Enum):
    # Geometry
    BOUNDARY_OFFSET = "BOUNDARY_OFFSET"
    AREA_MISMATCH = "AREA_MISMATCH"
    OVERLAP = "OVERLAP"
    GAP = "GAP"
    SHAPE_DEFORMATION = "SHAPE_DEFORMATION"
    # CRS
    MISSING_CRS = "MISSING_CRS"
    AXIS_ORDER = "AXIS_ORDER"
    DATUM_MISMATCH = "DATUM_MISMATCH"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    # Attribute
    OWNER_REFERENCE_MISMATCH = "OWNER_REFERENCE_MISMATCH"
    LAND_USE_MISMATCH = "LAND_USE_MISMATCH"
    AREA_ATTRIBUTE_MISMATCH = "AREA_ATTRIBUTE_MISMATCH"
    IDENTIFIER_MISMATCH = "IDENTIFIER_MISMATCH"
    # Temporal
    OUTDATED_SOURCE = "OUTDATED_SOURCE"
    CONCURRENT_CONFLICT = "CONCURRENT_CONFLICT"
    UNRESOLVED_CHANGE = "UNRESOLVED_CHANGE"
    # Provenance
    SHARED_ORIGIN = "SHARED_ORIGIN"
    UNKNOWN_LINEAGE = "UNKNOWN_LINEAGE"
    # Cross-layer
    BUILDING_OUTSIDE_PARCEL = "BUILDING_OUTSIDE_PARCEL"
    UTILITY_CROSSING = "UTILITY_CROSSING"
    ROAD_ROW_CONFLICT = "ROAD_ROW_CONFLICT"
    ADMIN_BOUNDARY_CONFLICT = "ADMIN_BOUNDARY_CONFLICT"


class ConflictSeverity(str, Enum):
    CRITICAL = "CRITICAL"   # blocks auto-approval
    HIGH = "HIGH"           # requires review
    MEDIUM = "MEDIUM"       # review recommended
    LOW = "LOW"             # auto-resolvable


class DecisionState(str, Enum):
    PENDING = "PENDING"
    AUTO_APPROVED = "AUTO_APPROVED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"


class MatchMethod(str, Enum):
    SPATIAL_OVERLAP = "SPATIAL_OVERLAP"
    IDENTIFIER_EXACT = "IDENTIFIER_EXACT"
    SPATIAL_IDENTIFIER = "SPATIAL_IDENTIFIER"
    MULTI_SIGNAL = "MULTI_SIGNAL"


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic models (API + internal use)
# ─────────────────────────────────────────────────────────────────────────────

class SourceRecord(BaseModel):
    """A single raw record from one source dataset."""
    record_id: str
    source_type: SourceType
    source_dataset_id: str
    geometry: dict                          # GeoJSON geometry
    source_crs: str = "EPSG:4326"
    attributes: dict[str, Any] = Field(default_factory=dict)
    capture_timestamp: Optional[str] = None
    ingest_timestamp: Optional[str] = None
    provenance_node_id: Optional[str] = None
    content_hash: Optional[str] = None
    quality_level: DataQualityLevel = DataQualityLevel.UNKNOWN


class DatasetProfile(BaseModel):
    """Data quality profile for an ingested dataset."""
    dataset_id: str
    source_type: SourceType
    total_features: int = 0
    valid_geometries: int = 0
    invalid_geometries: int = 0
    duplicate_ids: int = 0
    missing_timestamps: int = 0
    missing_attributes: dict[str, int] = Field(default_factory=dict)
    crs_declared: Optional[str] = None
    crs_issues: int = 0
    completeness_pct: float = 0.0
    quality_level: DataQualityLevel = DataQualityLevel.UNKNOWN
    schema_fields: list[str] = Field(default_factory=list)
    content_hash: Optional[str] = None


class CanonicalParcel(BaseModel):
    """The canonical representation of a parcel after matching."""
    canonical_id: str
    ulpin: Optional[str] = None
    geometry: Optional[dict] = None         # best-estimate geometry (WGS84)
    area_sqm: Optional[float] = None
    centroid: Optional[dict] = None
    land_use: Optional[str] = None
    owner_reference: Optional[str] = None
    status: str = "ACTIVE"
    source_record_ids: list[str] = Field(default_factory=list)
    match_method: Optional[MatchMethod] = None
    match_confidence: Optional[float] = None
    match_evidence: dict = Field(default_factory=dict)
    independent_lineages: int = 0
    conflicts: list[str] = Field(default_factory=list)  # conflict_ids
    proposal_id: Optional[str] = None
    version: int = 1
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ConflictRecord(BaseModel):
    """A detected conflict between source records for a parcel."""
    conflict_id: str
    parcel_id: str
    conflict_type: ConflictType
    severity: ConflictSeverity
    record_ids: list[str]
    measure: Optional[float] = None         # e.g. boundary offset in metres
    measure_unit: Optional[str] = None
    description: str = ""
    evidence: dict = Field(default_factory=dict)
    auto_resolvable: bool = False
    status: str = "OPEN"


class HarmonizationProposal(BaseModel):
    """A proposed harmonization for a canonical parcel."""
    proposal_id: str
    parcel_id: str
    version: int = 1
    proposed_geometry: Optional[dict] = None    # GeoJSON
    proposed_attributes: dict = Field(default_factory=dict)
    change_summary: list[str] = Field(default_factory=list)
    conflicts_resolved: list[str] = Field(default_factory=list)
    conflicts_unresolved: list[str] = Field(default_factory=list)
    match_confidence: float = 0.0
    confidence_components: dict = Field(default_factory=dict)
    independent_lineages: int = 0
    decision: DecisionState = DecisionState.PENDING
    decision_reason: str = ""
    decision_actor: Optional[str] = None
    decision_timestamp: Optional[str] = None
    ripple_check: dict = Field(default_factory=dict)
    evidence_hash: Optional[str] = None
    signature: Optional[str] = None


class RippleCheckResult(BaseModel):
    """Result of checking downstream impact of a proposed change."""
    proposal_id: str
    safe_to_auto_approve: bool
    affected_parcels: list[dict] = Field(default_factory=list)
    affected_layers: list[dict] = Field(default_factory=list)
    total_issues: int = 0
    critical_issues: int = 0
    details: list[str] = Field(default_factory=list)


class ReviewQueueItem(BaseModel):
    """An item in the officer review queue."""
    item_id: str
    proposal_id: str
    parcel_id: str
    priority: int = 0       # higher = more urgent
    reason: str = ""
    conflict_summary: list[str] = Field(default_factory=list)
    created_at: str = ""
    assigned_to: Optional[str] = None
    status: str = "PENDING"


class AuditEvent(BaseModel):
    """An immutable audit log entry."""
    event_id: str
    timestamp_utc: str
    case_id: str
    event_type: str
    actor: str
    details: dict = Field(default_factory=dict)
    hash: Optional[str] = None
