"""
Judge Agent.

Combines all stage outputs and the six specialist agent verdicts into the
single FinalVerdict — the only object the rest of the platform (API, UI)
needs to consume. Produces:
- claim_status (supported / contradicted / not_enough_information)
- severity
- risk_flags (deduplicated union of every stage's flags)
- all named scores from the spec's "Final Outputs" section
- a chain of evidence (auditable, references specific images/video/metadata)
- a final_justification narrative (LLM-enhanced if Ollama available, else
  template-based — always present, never blank)
- requires_manual_review boolean
"""
from __future__ import annotations
from typing import List

from app.core.schemas import (
    FinalVerdict, ClaimStatus, Severity, RiskFlag, ChainOfEvidenceItem, AgentVerdict,
    AuthenticityEngineOutput, OwnershipEngineOutput, PossessionEngineOutput,
    LivenessEngineOutput, SufficiencyEngineOutput, VisionAnalysisOutput,
    StoryConsistencyOutput, PhysicsValidationOutput, UserRiskOutput,
    FraudNetworkOutput, TemporalGeoOutput, PerImageVerdictSummary,
)
from app.utils.ollama_client import query_text_model, is_ollama_available
from app.agents.fraud_explanation import explain_image_authenticity

# Manual review trigger thresholds — tuned conservative: false negatives
# (a real fraud slipping through to auto-approval) are costlier than false
# positives (an honest claim getting a human look), so the bar for
# "requires_manual_review" is intentionally low.
MANUAL_REVIEW_FRAUD_THRESHOLD = 0.45
MANUAL_REVIEW_TRUST_FLOOR = 0.5


def _build_chain_of_evidence(
    vision: VisionAnalysisOutput,
    authenticity: AuthenticityEngineOutput,
    liveness: LivenessEngineOutput,
    physics: PhysicsValidationOutput,
    story: StoryConsistencyOutput,
) -> List[ChainOfEvidenceItem]:
    chain = []
    for i, obs in enumerate(vision.observations, start=1):
        chain.append(ChainOfEvidenceItem(source=f"image_{i}", observation=obs.objective_description))
    for i, pi in enumerate(authenticity.per_image, start=1):
        if pi.image_authenticity_score < 0.5:
            chain.append(ChainOfEvidenceItem(
                source=f"image_{i}_forensics",
                observation=f"Authenticity score {pi.image_authenticity_score}: ELA manipulation score "
                            f"{pi.ela.manipulation_score}, AI-generation probability {pi.ai_generated.ai_generation_probability}.",
            ))
    if liveness.video_provided:
        chain.append(ChainOfEvidenceItem(
            source="video",
            observation=f"Liveness score {liveness.damage_liveness_score}: motion naturalness "
                        f"{liveness.motion_naturalness_score}, object consistency across frames: {liveness.damage_consistent_across_frames}.",
        ))
    chain.append(ChainOfEvidenceItem(
        source="physics_validation",
        observation=f"Fracture pattern classified as '{physics.fracture_pattern}', "
                    f"impact point detected: {physics.impact_point_detected}, plausibility score {physics.damage_authenticity_score}.",
    ))
    chain.append(ChainOfEvidenceItem(source="story_consistency", observation=story.reasoning))
    return chain


def _determine_claim_status(
    story: StoryConsistencyOutput, vision: VisionAnalysisOutput, sufficiency: SufficiencyEngineOutput,
    authenticity: AuthenticityEngineOutput,
) -> ClaimStatus:
    if sufficiency.coverage_score < 0.4 or not vision.observations:
        return ClaimStatus.not_enough_information
    if not story.is_consistent or authenticity.authenticity_score < 0.3:
        return ClaimStatus.contradicted
    if vision.aggregate_severity == Severity.unknown and not vision.aggregate_issue:
        return ClaimStatus.not_enough_information
    return ClaimStatus.supported


def _generate_justification(
    claim_status: ClaimStatus, chain: List[ChainOfEvidenceItem], flags: List[RiskFlag],
) -> str:
    chain_summary = "; ".join(f"{c.source}: {c.observation}" for c in chain[:6])
    default = (
        f"The claim is assessed as '{claim_status.value}'. "
        f"Supporting observations — {chain_summary}. "
        + (f"Risk flags raised: {', '.join(f.value for f in flags)}." if flags else "No risk flags were raised.")
    )

    if not is_ollama_available():
        return default

    prompt = (
        "Write a concise, professional final justification paragraph (3-5 sentences) for an "
        "insurance claim decision, for the case file. Be factual and reference the evidence given. "
        "Do not invent any facts beyond what is provided.\n\n"
        f"Claim status: {claim_status.value}\n"
        f"Risk flags: {[f.value for f in flags]}\n"
        f"Evidence chain: {chain_summary}"
    )
    try:
        result = query_text_model(prompt).strip()
        return result if result else default
    except Exception:
        return default


def render_verdict(
    claim_id: str,
    vision: VisionAnalysisOutput,
    authenticity: AuthenticityEngineOutput,
    ownership: OwnershipEngineOutput,
    possession: PossessionEngineOutput,
    liveness: LivenessEngineOutput,
    sufficiency: SufficiencyEngineOutput,
    story: StoryConsistencyOutput,
    physics: PhysicsValidationOutput,
    user_risk: UserRiskOutput,
    fraud_network: FraudNetworkOutput,
    temporal_geo: TemporalGeoOutput,
    agent_verdicts: List[AgentVerdict],
) -> FinalVerdict:
    all_flags: List[RiskFlag] = []
    for source in (authenticity.flags, ownership.flags, possession.flags, liveness.flags,
                   sufficiency.flags, story.flags, physics.flags, user_risk.flags,
                   fraud_network.flags, temporal_geo.flags):
        all_flags.extend(source)
    for av in agent_verdicts:
        all_flags.extend(av.flags)
    all_flags = list(dict.fromkeys(all_flags))

    fraud_agent = next((a for a in agent_verdicts if a.agent_name == "Fraud Expert"), None)
    fraud_probability = fraud_agent.score if fraud_agent else 0.0

    overall_trust = round(
        0.20 * authenticity.authenticity_score
        + 0.15 * ownership.ownership_score
        + 0.15 * possession.possession_score
        + 0.15 * sufficiency.coverage_score
        + 0.15 * story.consistency_score
        + 0.10 * physics.damage_authenticity_score
        + 0.10 * (1.0 - user_risk.claimant_risk_score),
        3,
    )
    # Fraud network and confirmed temporal/geo contradictions act as hard
    # penalties on top of the weighted average — these are strong enough
    # signals that they shouldn't just be diluted into an average.
    if fraud_network.network_risk_score > 0.5:
        overall_trust = round(overall_trust * (1.0 - 0.4 * fraud_network.network_risk_score), 3)
    if temporal_geo.timestamp_before_policy:
        overall_trust = round(overall_trust * 0.5, 3)

    claim_status = _determine_claim_status(story, vision, sufficiency, authenticity)
    chain = _build_chain_of_evidence(vision, authenticity, liveness, physics, story)
    justification = _generate_justification(claim_status, chain, all_flags)

    per_image_summary = []
    for pi in authenticity.per_image:
        explanation = explain_image_authenticity(pi)
        per_image_summary.append(PerImageVerdictSummary(
            image_path=pi.image_path,
            image_authenticity_score=pi.image_authenticity_score,
            ela_manipulation_score=pi.ela.manipulation_score,
            ai_generation_probability=pi.ai_generated.ai_generation_probability,
            lighting_consistency_score=pi.reflection.lighting_consistency_score,
            notes=pi.ai_generated.signals + pi.reflection.notes + pi.metadata.metadata_flags,
            fraud_verdict=explanation.verdict,
            fraud_headline=explanation.headline,
            fraud_evidence=[e.model_dump() for e in explanation.evidence],
        ))

    requires_manual_review = (
        fraud_probability >= MANUAL_REVIEW_FRAUD_THRESHOLD
        or overall_trust < MANUAL_REVIEW_TRUST_FLOOR
        or claim_status == ClaimStatus.contradicted
        or RiskFlag.duplicate_claim_network in all_flags
        or RiskFlag.timestamp_before_policy_start in all_flags
        or user_risk.risk_level.value in ("high", "very_high")
    )

    return FinalVerdict(
        claim_id=claim_id,
        claim_status=claim_status,
        severity=vision.aggregate_severity,
        risk_flags=all_flags,
        authenticity_score=authenticity.authenticity_score,
        ownership_score=ownership.ownership_score,
        possession_score=possession.possession_score,
        damage_liveness_score=liveness.damage_liveness_score,
        evidence_coverage_score=sufficiency.coverage_score,
        claimant_risk_score=user_risk.claimant_risk_score,
        fraud_probability=fraud_probability,
        overall_claim_trust_score=max(0.0, min(1.0, overall_trust)),
        chain_of_evidence=chain,
        final_justification=justification,
        requires_manual_review=requires_manual_review,
        agent_verdicts=agent_verdicts,
        per_image_summary=per_image_summary,
        fraud_network_duplicate_claim_ids=fraud_network.duplicate_image_claim_ids,
        fraud_network_shared_identifier_claim_ids=fraud_network.shared_serial_claim_ids,
    )
