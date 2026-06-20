"""
Master Pipeline Orchestrator.

Runs every stage in the correct order for a single claim and produces the
FinalVerdict. This is the single entry point the API layer calls.

Order matters and mirrors the spec exactly:
  Stage 0  -> Evidence Authenticity (runs BEFORE damage detection)
  Stage 1  -> Ownership Verification
  Stage 2  -> Possession Verification (challenge code)
  Stage 3  -> Damage Liveness (video)
  Stage 4  -> Evidence Sufficiency
  Stage 5  -> Vision-Language Analysis (blind to claim text)
  Stage 6  -> Claim Understanding (NLP on claim text)
  Stage 7  -> Story Consistency (cross-check Stage 5 vs Stage 6)
  Stage 8  -> Physics-Based Damage Validation
  Stage 9  -> User Risk Engine
  Stage 10 -> Adaptive Verification
  Bonus    -> Temporal/Geo Consistency, Fraud Network Detection
  Stage 11 -> Multi-Agent Investigation + Judge
"""
from __future__ import annotations
from typing import Optional

from app.core.schemas import ClaimRecord, FinalVerdict
from app.stages.stage0_orchestrator import run_authenticity_engine
from app.stages.stage1_ownership import run_ownership_engine
from app.stages.stage2_possession import run_possession_engine
from app.stages.stage3_liveness import run_liveness_engine
from app.stages.stage4_sufficiency import run_sufficiency_engine
from app.stages.stage5_vision import run_vision_analysis
from app.stages.stage6_claim_understanding import run_claim_understanding
from app.stages.stage7_story_consistency import run_story_consistency_engine
from app.stages.stage8_physics import analyze_fracture_pattern
from app.stages.stage9_user_risk import run_user_risk_engine
from app.stages.stage10_adaptive import run_adaptive_verification
from app.stages.stageX_temporal_geo import run_temporal_geo_engine
from app.stages.stageX_fraud_network import run_fraud_network_engine
from app.agents.specialist_agents import run_all_agents
from app.agents.judge import render_verdict


def run_full_pipeline(
    claim: ClaimRecord,
    past_claim_count: int = 0,
    rejected_claim_count: int = 0,
    history_flags: Optional[list] = None,
) -> FinalVerdict:
    history_flags = history_flags or []
    image_paths = claim.image_paths
    sub = claim.submission

    # Stage 0
    authenticity = run_authenticity_engine(image_paths)

    # Stage 1
    ownership = run_ownership_engine(
        image_paths, sub.user_provided_model, sub.user_provided_serial,
        sub.user_provided_plate, sub.user_provided_vin,
    )

    # Stage 2
    possession = run_possession_engine(image_paths, claim.challenge_code or "")

    # Stage 3
    liveness = run_liveness_engine(claim.video_path)

    # Stage 6 first (need claimed part/issue to inform Stage 4's requirements)
    claim_understanding = run_claim_understanding(sub.user_claim, sub.claim_object.value)

    # Stage 4
    sufficiency = run_sufficiency_engine(
        image_paths, sub.claim_object.value, claim_understanding.claimed_part, claim_understanding.claimed_issue,
    )

    # Stage 5 (must not see claim text — only claim_object is passed for taxonomy scoping)
    vision = run_vision_analysis(image_paths, sub.claim_object.value)

    # Stage 7
    story = run_story_consistency_engine(claim_understanding, vision, sub.claim_object.value)

    # Stage 8 (run on first image as primary evidence; in production, run per-image and aggregate)
    physics = analyze_fracture_pattern(image_paths[0]) if image_paths else analyze_fracture_pattern("")

    # Stage 9
    user_risk = run_user_risk_engine(past_claim_count, rejected_claim_count, history_flags)

    # Stage 10
    adaptive = run_adaptive_verification(
        user_risk.risk_level, bool(image_paths), bool(claim.video_path),
        possession.challenge_code_detected, ownership.matches_user_provided_details,
    )

    # Bonus stages
    temporal_geo = run_temporal_geo_engine(
        [pi.metadata for pi in authenticity.per_image], sub.policy_start_date, sub.registered_region,
    )
    fraud_network = run_fraud_network_engine(
        claim.claim_id, sub.user_id, image_paths,
        ownership.evidence.detected_serial, ownership.evidence.detected_vin, ownership.evidence.detected_plate,
    )

    # Stage 11 — agents + judge
    agent_verdicts = run_all_agents(
        vision, authenticity, sufficiency, story, physics, fraud_network,
        liveness, temporal_geo, user_risk, ownership, possession,
    )

    verdict = render_verdict(
        claim.claim_id, vision, authenticity, ownership, possession, liveness,
        sufficiency, story, physics, user_risk, fraud_network, temporal_geo, agent_verdicts,
    )

    return verdict
