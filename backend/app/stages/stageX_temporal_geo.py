"""
Bonus Stage — Temporal & Geo Consistency Engine.

Two real, high-value fraud signals not in the original spec but extremely
common in actual insurance fraud:

1. Timestamp-before-policy-start: the EXIF capture timestamp of the damage
   photo predates the policy's start date — meaning the damage existed
   BEFORE coverage began. This is one of the single highest-value fraud
   signals available, and it is purely a metadata cross-check (no ML needed).

2. Geo mismatch: the photo's EXIF GPS location is inconsistent with the
   claimant's registered region (e.g. claim filed for a car registered in
   Pune, but the photo's GPS metadata places it in a different country).
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List

from app.core.schemas import TemporalGeoOutput, MetadataReport, RiskFlag

EXIF_DATETIME_FORMATS = ["%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in EXIF_DATETIME_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            continue
    return None


# Extremely coarse region->bounding-box lookup for demo purposes. In
# production, swap this for a real reverse-geocoding service or a proper
# geofence per policy region.
REGION_BOUNDING_BOXES = {
    "pune": (18.3, 18.7, 73.7, 74.0),       # (lat_min, lat_max, lon_min, lon_max)
    "mumbai": (18.9, 19.3, 72.7, 73.1),
    "delhi": (28.4, 28.9, 76.8, 77.4),
    "bangalore": (12.8, 13.2, 77.4, 77.8),
}


def run_temporal_geo_engine(
    metadata_reports: List[MetadataReport],
    policy_start_date: Optional[str],
    registered_region: Optional[str],
) -> TemporalGeoOutput:
    flags = []
    photo_timestamp = None
    photo_gps = None

    for m in metadata_reports:
        if m.timestamp and not photo_timestamp:
            photo_timestamp = m.timestamp
        if m.gps_latitude is not None and m.gps_longitude is not None and not photo_gps:
            photo_gps = {"latitude": m.gps_latitude, "longitude": m.gps_longitude}

    timestamp_before_policy = False
    photo_dt = _parse_dt(photo_timestamp)
    policy_dt = _parse_dt(policy_start_date)
    if photo_dt and policy_dt and photo_dt < policy_dt:
        timestamp_before_policy = True
        flags.append(RiskFlag.timestamp_before_policy_start)

    geo_mismatch = False
    if photo_gps and registered_region:
        region_key = registered_region.strip().lower()
        bbox = REGION_BOUNDING_BOXES.get(region_key)
        if bbox:
            lat_min, lat_max, lon_min, lon_max = bbox
            in_box = (
                lat_min <= photo_gps["latitude"] <= lat_max
                and lon_min <= photo_gps["longitude"] <= lon_max
            )
            geo_mismatch = not in_box
            if geo_mismatch:
                flags.append(RiskFlag.geo_location_mismatch)

    return TemporalGeoOutput(
        photo_timestamp=photo_timestamp,
        claim_submission_time=datetime.utcnow().isoformat(),
        policy_start_date=policy_start_date,
        timestamp_before_policy=timestamp_before_policy,
        photo_gps=photo_gps,
        registered_region=registered_region,
        geo_mismatch=geo_mismatch,
        flags=flags,
    )
