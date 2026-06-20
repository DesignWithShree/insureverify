"""
Stage 0 — Evidence Authenticity Engine
Part A: Metadata / EXIF forensics.

Extracts EXIF metadata from an image and flags signals commonly associated
with manipulated, AI-generated, or non-original (e.g. screenshot-of-a-
screenshot, downloaded-from-internet) images.
"""
from __future__ import annotations
import io
from typing import Optional
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

from app.core.schemas import MetadataReport

# Software strings strongly associated with image editing / generation.
EDITING_SOFTWARE_SIGNATURES = [
    "photoshop", "gimp", "lightroom", "affinity photo", "pixelmator",
    "snapseed", "facetune", "picsart", "canva",
]

AI_GENERATION_SOFTWARE_SIGNATURES = [
    "midjourney", "dall-e", "dalle", "stable diffusion", "comfyui",
    "automatic1111", "leonardo.ai", "firefly",
]


def _decimal_from_dms(dms, ref) -> Optional[float]:
    try:
        degrees = dms[0][0] / dms[0][1]
        minutes = dms[1][0] / dms[1][1]
        seconds = dms[2][0] / dms[2][1]
        value = degrees + minutes / 60.0 + seconds / 3600.0
        if ref in ("S", "W"):
            value = -value
        return value
    except Exception:
        return None


def extract_metadata(image_path: str) -> MetadataReport:
    flags: list[str] = []
    report = MetadataReport()

    try:
        img = Image.open(image_path)
        exif_data = img._getexif() if hasattr(img, "_getexif") else None
    except Exception as e:
        flags.append(f"failed_to_open_image:{e}")
        report.metadata_flags = flags
        report.suspicious_metadata = True
        return report

    if not exif_data:
        # Absence of EXIF is itself a weak signal — most camera/phone photos
        # carry EXIF. Screenshots, re-saved images, and many AI-generated
        # images strip it entirely. Not conclusive on its own.
        flags.append("no_exif_data_present")
        report.has_exif = False
        report.suspicious_metadata = True
        report.metadata_flags = flags
        return report

    report.has_exif = True
    exif = {}
    gps_info = {}
    for tag_id, value in exif_data.items():
        tag = TAGS.get(tag_id, tag_id)
        if tag == "GPSInfo":
            for gps_tag_id, gps_val in value.items():
                gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                gps_info[gps_tag] = gps_val
        else:
            exif[tag] = value

    camera_make = exif.get("Make")
    camera_model_tag = exif.get("Model")
    if camera_make or camera_model_tag:
        report.camera_model = f"{camera_make or ''} {camera_model_tag or ''}".strip()
    else:
        flags.append("no_camera_model_in_exif")

    timestamp = exif.get("DateTimeOriginal") or exif.get("DateTime")
    if timestamp:
        report.timestamp = str(timestamp)
    else:
        flags.append("no_capture_timestamp_in_exif")

    software = str(exif.get("Software", "")).lower()
    if software:
        report.editing_software = software
        for sig in EDITING_SOFTWARE_SIGNATURES:
            if sig in software:
                flags.append(f"editing_software_detected:{sig}")
        for sig in AI_GENERATION_SOFTWARE_SIGNATURES:
            if sig in software:
                flags.append(f"ai_generation_software_detected:{sig}")

    if gps_info:
        lat = _decimal_from_dms(gps_info.get("GPSLatitude"), gps_info.get("GPSLatitudeRef"))
        lon = _decimal_from_dms(gps_info.get("GPSLongitude"), gps_info.get("GPSLongitudeRef"))
        report.gps_latitude = lat
        report.gps_longitude = lon

    # Heuristic: DateTime present but DateTimeOriginal absent + Software
    # present often indicates the file was re-processed/re-saved after capture.
    if exif.get("DateTime") and not exif.get("DateTimeOriginal") and software:
        flags.append("resaved_after_capture_signature")

    report.suspicious_metadata = len(flags) > 0
    report.metadata_flags = flags
    return report
