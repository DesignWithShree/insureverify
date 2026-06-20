"""
Bonus Stage — Fraud Network / Duplicate Network Engine.

This is the platform's "fraud ring" detector. It looks ACROSS claims (not
just within a single claim) for patterns that single-claim analysis cannot
see:

1. The exact same evidence photo (via pHash) reused across multiple claims
   — whether by the same user (resubmitting old damage) or by different
   users entirely (a shared/leaked stock photo of "damage" circulating
   among a fraud ring).
2. The same device serial/VIN/plate appearing on claims filed by DIFFERENT
   user_ids — a strong signal of identity reuse or a coordinated ring
   filing multiple claims against what is actually one object.

This stage is what makes the platform genuinely systematic about fraud
detection rather than only judging each claim in isolation, which is the
single biggest blind spot of most "is there damage" CV systems.
"""
from __future__ import annotations
from typing import List, Optional

from app.core.schemas import FraudNetworkOutput, RiskFlag, ClaimRecord
from app.stages.stage0_phash import compute_phash, hamming_distance
from app.db.claims_store import list_claims_excluding


def run_fraud_network_engine(
    claim_id: str,
    user_id: str,
    image_paths: List[str],
    detected_serial: Optional[str],
    detected_vin: Optional[str],
    detected_plate: Optional[str],
) -> FraudNetworkOutput:
    other_claims = list_claims_excluding(claim_id)
    current_hashes = [compute_phash(p) for p in image_paths]

    duplicate_claim_ids = set()
    shared_serial_claim_ids = set()
    shared_device_other_users = set()

    for other in other_claims:
        # --- Duplicate image detection across claims ---
        for other_path in other.image_paths:
            other_hash = compute_phash(other_path)
            for ch in current_hashes:
                if ch and other_hash and hamming_distance(ch, other_hash) <= 8:
                    duplicate_claim_ids.add(other.claim_id)

        # --- Shared identifier detection across claims ---
        other_submission = other.submission
        identifiers_match = False
        if detected_serial and other_submission.user_provided_serial:
            if detected_serial.upper().replace(" ", "") == other_submission.user_provided_serial.upper().replace(" ", ""):
                identifiers_match = True
        if detected_vin and other_submission.user_provided_vin:
            if detected_vin.upper() == other_submission.user_provided_vin.upper():
                identifiers_match = True
        if detected_plate and other_submission.user_provided_plate:
            if detected_plate.upper().replace(" ", "") == other_submission.user_provided_plate.upper().replace(" ", ""):
                identifiers_match = True

        if identifiers_match:
            shared_serial_claim_ids.add(other.claim_id)
            if other_submission.user_id != user_id:
                shared_device_other_users.add(other_submission.user_id)

    flags = []
    if duplicate_claim_ids:
        flags.append(RiskFlag.duplicate_claim_network)
        flags.append(RiskFlag.reused_claim_photo)
    if shared_device_other_users:
        flags.append(RiskFlag.duplicate_claim_network)
        flags.append(RiskFlag.inconsistent_serial_number)

    network_risk_score = 0.0
    network_risk_score += min(len(duplicate_claim_ids) * 0.3, 0.6)
    network_risk_score += min(len(shared_device_other_users) * 0.4, 0.8)
    network_risk_score = round(min(network_risk_score, 1.0), 3)

    return FraudNetworkOutput(
        duplicate_image_claim_ids=list(duplicate_claim_ids),
        shared_serial_claim_ids=list(shared_serial_claim_ids),
        shared_device_other_users=list(shared_device_other_users),
        network_risk_score=network_risk_score,
        flags=list(dict.fromkeys(flags)),
    )
