"""
Stage 9 — User Risk Engine.

Calculates a claimant risk score from historical claim behavior (past claim
count, rejected claim count, flags from prior investigations). This score
feeds Stage 10 (Adaptive Verification) to decide how much extra evidence to
demand from this specific claimant.
"""
from __future__ import annotations
from typing import List

from app.core.schemas import UserRiskOutput, RiskLevel, RiskFlag


def run_user_risk_engine(
    past_claim_count: int, rejected_claim_count: int, history_flags: List[str],
) -> UserRiskOutput:
    rejection_rate = round(rejected_claim_count / past_claim_count, 3) if past_claim_count > 0 else 0.0

    score = 0.0
    score += min(rejection_rate * 0.6, 0.6)
    score += min(len(history_flags) * 0.1, 0.3)
    if past_claim_count >= 5 and rejection_rate > 0.4:
        score += 0.1  # repeated-offender pattern, not just one bad claim
    score = round(min(score, 1.0), 3)

    if score < 0.25:
        risk_level = RiskLevel.low
    elif score < 0.5:
        risk_level = RiskLevel.medium
    elif score < 0.75:
        risk_level = RiskLevel.high
    else:
        risk_level = RiskLevel.very_high

    flags = [RiskFlag.high_risk_claimant_history] if risk_level in (RiskLevel.high, RiskLevel.very_high) else []

    return UserRiskOutput(
        past_claim_count=past_claim_count,
        rejected_claim_count=rejected_claim_count,
        rejection_rate=rejection_rate,
        history_flags=history_flags,
        claimant_risk_score=score,
        risk_level=risk_level,
        flags=flags,
    )
