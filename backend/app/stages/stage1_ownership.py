"""
Stage 1 — Ownership Verification Engine.

Uses OCR (EasyOCR) to read identifying text from evidence images — serial
numbers, model numbers, VINs, number plates — and cross-checks against what
the claimant declared at submission time. A mismatch here is one of the
strongest fraud signals in the entire pipeline (it means the claimant is
either not looking at their own device/vehicle, or is using someone else's
identifying details).
"""
from __future__ import annotations
import re
from typing import List, Optional

from app.core.schemas import OwnershipEngineOutput, OwnershipEvidence, RiskFlag
from app.utils.ocr import extract_text

# VIN: 17 chars, no I/O/Q, alphanumeric.
VIN_PATTERN = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b")

# Indian-style number plate, e.g. MH12AB1234 — adjust/extend for other formats.
PLATE_PATTERN = re.compile(r"\b[A-Z]{2}[\s-]?\d{1,2}[\s-]?[A-Z]{1,3}[\s-]?\d{3,4}\b")

# Generic serial-number-looking token: long alphanumeric strings, often with
# a mix of letters and digits, length >= 6.
SERIAL_PATTERN = re.compile(r"\b(?=[A-Z0-9]{6,20}\b)(?=.*[A-Z])(?=.*\d)[A-Z0-9]{6,20}\b")

KNOWN_LAPTOP_BRANDS = ["dell", "hp", "lenovo", "asus", "acer", "apple", "macbook", "msi", "samsung", "lg"]


def _normalize(text: str) -> str:
    return text.upper().replace(" ", "").strip()


def parse_ownership_evidence(detected_texts: List[str]) -> OwnershipEvidence:
    evidence = OwnershipEvidence(detected_text=detected_texts)
    joined = " ".join(detected_texts)
    joined_upper = joined.upper()

    for brand in KNOWN_LAPTOP_BRANDS:
        if brand.upper() in joined_upper:
            evidence.detected_brand = brand
            break

    vin_match = VIN_PATTERN.search(joined_upper.replace(" ", ""))
    if vin_match:
        evidence.detected_vin = vin_match.group(0)

    plate_match = PLATE_PATTERN.search(joined_upper)
    if plate_match:
        evidence.detected_plate = plate_match.group(0).replace(" ", "").replace("-", "")

    for token in detected_texts:
        norm = _normalize(token)
        if SERIAL_PATTERN.match(norm) and norm != evidence.detected_vin:
            evidence.detected_serial = norm
            break

    return evidence


def run_ownership_engine(
    image_paths: List[str],
    user_provided_model: Optional[str],
    user_provided_serial: Optional[str],
    user_provided_plate: Optional[str],
    user_provided_vin: Optional[str],
) -> OwnershipEngineOutput:
    all_text: List[str] = []
    for path in image_paths:
        all_text.extend(extract_text(path))

    evidence = parse_ownership_evidence(all_text)
    notes = []
    flags = []
    matched_fields = 0
    checked_fields = 0

    def _check(user_value, detected_value, label):
        nonlocal matched_fields, checked_fields
        if user_value:
            checked_fields += 1
            if detected_value and _normalize(user_value) == _normalize(detected_value):
                matched_fields += 1
                notes.append(f"{label}_matches_user_declaration")
            elif detected_value:
                notes.append(f"{label}_MISMATCH_user_said='{user_value}'_detected='{detected_value}'")
            else:
                notes.append(f"{label}_not_detected_in_evidence_to_verify_against")

    _check(user_provided_serial, evidence.detected_serial, "serial_number")
    _check(user_provided_vin, evidence.detected_vin, "vin")
    _check(user_provided_plate, evidence.detected_plate, "number_plate")
    if user_provided_model and evidence.detected_brand:
        checked_fields += 1
        if evidence.detected_brand.lower() in user_provided_model.lower():
            matched_fields += 1
            notes.append("model_brand_matches_user_declaration")
        else:
            notes.append(f"model_brand_MISMATCH_user_said='{user_provided_model}'_detected='{evidence.detected_brand}'")

    has_mismatch = any("MISMATCH" in n for n in notes)
    if has_mismatch:
        flags.append(RiskFlag.inconsistent_serial_number)

    if checked_fields == 0:
        # No verifiable identifiers were provided at all — not necessarily
        # fraud, but it means ownership cannot be positively confirmed.
        ownership_score = 0.4
        notes.append("no_identifying_details_provided_for_cross_check")
        flags.append(RiskFlag.ownership_not_verified)
    else:
        ownership_score = round(matched_fields / checked_fields, 3)
        if ownership_score < 0.5:
            flags.append(RiskFlag.ownership_not_verified)

    matches = checked_fields > 0 and matched_fields == checked_fields

    return OwnershipEngineOutput(
        evidence=evidence,
        matches_user_provided_details=matches,
        ownership_score=ownership_score,
        flags=flags,
        notes=notes,
    )
