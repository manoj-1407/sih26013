"""SQLAlchemy database setup and table definitions.

Uses SQLite for portable/offline-first operation.
Designed to be swapped to PostGIS for production deployment
by changing the DATABASE_URL environment variable.
"""
from __future__ import annotations
import os
import json
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    create_engine, Column, String, Text, Float, Integer,
    Boolean, DateTime, JSON, ForeignKey, Index, event
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.sql import func

Base = declarative_base()


def _get_db_url() -> str:
    data_dir = os.environ.get("GS_DATA_DIR", str(Path(__file__).resolve().parents[3] / "data"))
    db_dir = Path(data_dir) / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_dir}/geosamanvay.db"


# ─────────────────────────────────────────────────────────────────────────────
# Table definitions
# ─────────────────────────────────────────────────────────────────────────────

class DBDataset(Base):
    __tablename__ = "datasets"
    dataset_id = Column(String, primary_key=True)
    case_id = Column(String, nullable=False, index=True)
    source_type = Column(String, nullable=False)
    label = Column(String, default="")
    authority = Column(String, default="")
    total_features = Column(Integer, default=0)
    valid_features = Column(Integer, default=0)
    crs_declared = Column(String, nullable=True)
    content_hash = Column(String, nullable=True)
    quality_level = Column(String, default="UNKNOWN")
    schema_fields = Column(JSON, default=list)
    profile = Column(JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now())

    records = relationship("DBSourceRecord", back_populates="dataset", cascade="all, delete-orphan")


class DBSourceRecord(Base):
    __tablename__ = "source_records"
    record_id = Column(String, primary_key=True)
    dataset_id = Column(String, ForeignKey("datasets.dataset_id"), nullable=False, index=True)
    case_id = Column(String, nullable=False, index=True)
    source_type = Column(String, nullable=False)
    geometry_wkt = Column(Text, nullable=True)      # WGS84 WKT
    geometry_geojson = Column(JSON, nullable=True)  # original GeoJSON
    source_crs = Column(String, default="EPSG:4326")
    attributes = Column(JSON, default=dict)
    capture_timestamp = Column(String, nullable=True)
    ingest_timestamp = Column(DateTime, server_default=func.now())
    provenance_node_id = Column(String, nullable=True)
    content_hash = Column(String, nullable=True)
    quality_level = Column(String, default="UNKNOWN")
    bbox_minx = Column(Float, nullable=True)
    bbox_miny = Column(Float, nullable=True)
    bbox_maxx = Column(Float, nullable=True)
    bbox_maxy = Column(Float, nullable=True)
    centroid_lon = Column(Float, nullable=True)
    centroid_lat = Column(Float, nullable=True)
    area_sqm = Column(Float, nullable=True)

    dataset = relationship("DBDataset", back_populates="records")

    __table_args__ = (
        Index("ix_source_records_case_source", "case_id", "source_type"),
        Index("ix_source_records_bbox", "bbox_minx", "bbox_miny", "bbox_maxx", "bbox_maxy"),
    )


class DBCanonicalParcel(Base):
    __tablename__ = "canonical_parcels"
    canonical_id = Column(String, primary_key=True)
    case_id = Column(String, nullable=False, index=True)
    ulpin = Column(String, nullable=True, index=True)
    geometry_wkt = Column(Text, nullable=True)
    geometry_geojson = Column(JSON, nullable=True)
    area_sqm = Column(Float, nullable=True)
    centroid_lon = Column(Float, nullable=True)
    centroid_lat = Column(Float, nullable=True)
    land_use = Column(String, nullable=True)
    owner_reference = Column(String, nullable=True)
    status = Column(String, default="ACTIVE")
    source_record_ids = Column(JSON, default=list)
    match_method = Column(String, nullable=True)
    match_confidence = Column(Float, nullable=True)
    match_evidence = Column(JSON, default=dict)
    independent_lineages = Column(Integer, default=0)
    conflict_ids = Column(JSON, default=list)
    proposal_id = Column(String, nullable=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    conflicts = relationship("DBConflict", back_populates="parcel", cascade="all, delete-orphan")
    proposals = relationship("DBProposal", back_populates="parcel", cascade="all, delete-orphan")


class DBConflict(Base):
    __tablename__ = "conflicts"
    conflict_id = Column(String, primary_key=True)
    parcel_id = Column(String, ForeignKey("canonical_parcels.canonical_id"), nullable=False, index=True)
    case_id = Column(String, nullable=False, index=True)
    conflict_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    record_ids = Column(JSON, default=list)
    measure = Column(Float, nullable=True)
    measure_unit = Column(String, nullable=True)
    description = Column(Text, default="")
    evidence = Column(JSON, default=dict)
    auto_resolvable = Column(Boolean, default=False)
    status = Column(String, default="OPEN")
    created_at = Column(DateTime, server_default=func.now())

    parcel = relationship("DBCanonicalParcel", back_populates="conflicts")


class DBProposal(Base):
    __tablename__ = "harmonization_proposals"
    proposal_id = Column(String, primary_key=True)
    parcel_id = Column(String, ForeignKey("canonical_parcels.canonical_id"), nullable=False, index=True)
    case_id = Column(String, nullable=False, index=True)
    version = Column(Integer, default=1)
    proposed_geometry_geojson = Column(JSON, nullable=True)
    proposed_attributes = Column(JSON, default=dict)
    change_summary = Column(JSON, default=list)
    conflicts_resolved = Column(JSON, default=list)
    conflicts_unresolved = Column(JSON, default=list)
    match_confidence = Column(Float, default=0.0)
    confidence_components = Column(JSON, default=dict)
    independent_lineages = Column(Integer, default=0)
    decision = Column(String, default="PENDING")
    decision_reason = Column(Text, default="")
    decision_actor = Column(String, nullable=True)
    decision_timestamp = Column(DateTime, nullable=True)
    ripple_check = Column(JSON, default=dict)
    evidence_hash = Column(String, nullable=True)
    signature = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    parcel = relationship("DBCanonicalParcel", back_populates="proposals")


class DBProvenanceNode(Base):
    __tablename__ = "provenance_nodes"
    node_id = Column(String, primary_key=True)
    case_id = Column(String, nullable=False, index=True)
    node_type = Column(String, nullable=False)
    parent_ids = Column(JSON, default=list)
    label = Column(String, default="")
    content_hash = Column(String, nullable=True)
    node_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now())


class DBCase(Base):
    __tablename__ = "cases"
    case_id = Column(String, primary_key=True)
    title = Column(String, default="")
    description = Column(Text, default="")
    status = Column(String, default="ACTIVE")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    case_metadata = Column("metadata", JSON, default=dict)


class DBAuditEvent(Base):
    __tablename__ = "audit_events"
    event_id = Column(String, primary_key=True)
    timestamp_utc = Column(String, nullable=False)
    case_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)
    actor = Column(String, default="system")
    details = Column(JSON, default=dict)
    event_hash = Column(String, nullable=True)  # SHA-256 of event content


# ─────────────────────────────────────────────────────────────────────────────
# Engine and session factory
# ─────────────────────────────────────────────────────────────────────────────

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        url = _get_db_url()
        _engine = create_engine(
            url,
            connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
            echo=False,
        )
        # Enable WAL mode for SQLite (better concurrent read performance)
        if url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def set_wal(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
        Base.metadata.create_all(_engine)
    return _engine


def get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


def get_db() -> Session:
    """FastAPI dependency: yields a database session."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
