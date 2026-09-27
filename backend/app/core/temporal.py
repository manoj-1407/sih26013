"""Temporal analysis for source records.

Determines whether a geometric discrepancy might be explained by
time elapsed between observations (temporally qualified discrepancy)
vs a genuine concurrent conflict.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timezone

from dateutil.parser import parse as parse_date, ParserError


# If sources are > TEMPORAL_QUALIFY_DAYS apart, conflict may be temporal
TEMPORAL_QUALIFY_DAYS = 365  # 1 year


@dataclass
class TemporalResult:
    valid: bool
    qualified: bool     # True if gap qualifies the conflict as temporal
    gap_days: float     # -1 if unknown
    timestamps: list[Optional[str]]
    reason: str


def parse_timestamp(ts: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 or common date formats. Returns None on failure."""
    if not ts:
        return None
    try:
        dt = parse_date(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        # Reject obviously wrong timestamps
        if dt.year < 1800 or dt > now:
            return None
        return dt
    except (ParserError, ValueError, OverflowError):
        return None


def analyze_temporal(
    ts_a: Optional[str],
    ts_b: Optional[str],
    qualify_days: float = TEMPORAL_QUALIFY_DAYS,
) -> TemporalResult:
    """Analyze temporal relationship between two records."""
    dt_a = parse_timestamp(ts_a)
    dt_b = parse_timestamp(ts_b)

    if dt_a is None or dt_b is None:
        missing = []
        if dt_a is None:
            missing.append("record A")
        if dt_b is None:
            missing.append("record B")
        reason = f"timestamp missing or unparseable for {', '.join(missing)}"
        # Fail-closed: missing timestamps = not qualified
        return TemporalResult(False, False, -1, [ts_a, ts_b], reason)

    gap = abs((dt_a - dt_b).total_seconds()) / 86400.0  # days
    qualified = gap > qualify_days

    reason = (
        f"Temporal gap {gap:.0f} days > {qualify_days:.0f} days threshold — "
        "conflict may reflect real change over time, not concurrent disagreement"
        if qualified
        else f"Temporal gap {gap:.0f} days — sources are concurrent"
    )
    return TemporalResult(True, qualified, round(gap, 1), [ts_a, ts_b], reason)


def classify_temporal_change(
    timestamps: list[Optional[str]],
) -> dict:
    """Classify a series of timestamps for change detection."""
    parsed = [parse_timestamp(ts) for ts in timestamps if ts]
    parsed = [dt for dt in parsed if dt is not None]
    if not parsed:
        return {"change_detected": False, "reason": "no valid timestamps"}
    parsed.sort()
    span_days = (parsed[-1] - parsed[0]).total_seconds() / 86400.0
    return {
        "change_detected": len(parsed) > 1,
        "earliest": parsed[0].isoformat(),
        "latest": parsed[-1].isoformat(),
        "span_days": round(span_days, 1),
        "observation_count": len(parsed),
    }
