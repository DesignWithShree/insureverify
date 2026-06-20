"""
Stage 10 — Adaptive Verification Engine.

Decides what additional evidence to demand based on the claimant's risk
level (from Stage 9) and combined fraud signals so far. Low-risk, clean
claims get a frictionless experience; high-risk claims get progressively
more verification friction. This is what makes the system fair to honest
claimants while still being rigorous on suspicious ones.
"""
from __future__ import annotations
from typing import List

from app.core.schemas import AdaptiveVerificationOutput, RiskLevel

REQUIREMENTS_BY_RISK = {
    RiskLevel.low: ["image_verification"],
    RiskLevel.medium: ["image_verification", "additional_photos"],
    RiskLevel.high: ["image_verification", "additional_photos", "challenge_video"],
    RiskLevel.very_high: [
        "image_verification", "additional_photos", "challenge_video",
        "ownership_verification", "challenge_code", "system_information", "video_verification",
    ],
}


def run_adaptive_verification(
    risk_level: RiskLevel,
    has_images: bool,
    has_video: bool,
    has_challenge_code_match: bool,
    has_ownership_match: bool,
) -> AdaptiveVerificationOutput:
    required = REQUIREMENTS_BY_RISK[risk_level]
    satisfied = []

    if has_images:
        satisfied.append("image_verification")
        satisfied.append("additional_photos")
    if has_video:
        satisfied.append("challenge_video")
        satisfied.append("video_verification")
    if has_challenge_code_match:
        satisfied.append("challenge_code")
    if has_ownership_match:
        satisfied.append("ownership_verification")
        satisfied.append("system_information")

    satisfied = [s for s in satisfied if s in required]
    pending = [r for r in required if r not in satisfied]

    return AdaptiveVerificationOutput(
        risk_level=risk_level,
        required_steps=required,
        satisfied_steps=list(dict.fromkeys(satisfied)),
        pending_steps=pending,
    )
