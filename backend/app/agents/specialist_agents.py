"""
Stage 11 — Multi-Agent Investigation Framework.

Six specialist agents each look at the SAME underlying stage outputs from
their own narrow lens and produce an AgentVerdict (a score + summary + any
flags they personally raise). The Judge Agent (in judge.py) then combines
all six into the final verdict.

Design note: each agent is implemented as a deterministic function over the
already-computed stage outputs (no redundant computation), optionally
enriched with an LLM-generated natural-language summary via llama3 if
Ollama is available. This keeps the agents fast, reproducible, and testable
without requiring Ollama to be running — the LLM only adds narrative
polish, never changes the underlying score.
"""
from __future__ import annotations
from typing import List

from app.core.schemas import (
    AgentVerdict, RiskFlag, Severity,
    AuthenticityEngineOutput, OwnershipEngineOutput, PossessionEngineOutput,
    SufficiencyEngineOutput, VisionAnalysisOutput, UserRiskOutput,
    FraudNetworkOutput, StoryConsistencyOutput, PhysicsValidationOutput,
    LivenessEngineOutput, TemporalGeoOutput,
)
from app.utils.ollama_client import query_text_model, is_ollama_available


def _llm_summary(agent_name: str, facts: str, default_summary: str) -> str:
    """LLM narration for individual agent summaries is intentionally
    disabled. Each agent call here would be a separate sequential Ollama
    round-trip (6 agents = 6 extra calls per claim) just to rephrase a
    sentence that is already fully determined by computed scores — no new
    analysis happens in that rephrasing. The template summary below is
    already factual and specific, so we skip the LLM call entirely and
    return it directly. (Kept as a function, rather than removed, so any of
    the six call sites below don't need to change if you want to
    re-enable per-agent narration later — see README "Extending the
    platform" for how to do that safely without reintroducing the latency.)
    """
    return default_summary


def vision_expert_agent(vision: VisionAnalysisOutput, physics: PhysicsValidationOutput) -> AgentVerdict:
    severity_weight = {Severity.none: 0.0, Severity.low: 0.3, Severity.medium: 0.6, Severity.high: 0.9, Severity.unknown: 0.4}
    confidence = sum(o.confidence for o in vision.observations) / len(vision.observations) if vision.observations else 0.0
    score = round(0.6 * severity_weight.get(vision.aggregate_severity, 0.4) + 0.4 * confidence, 3)

    default = (
        f"Observed {vision.aggregate_issue or 'no specific issue'} on "
        f"{vision.aggregate_part or 'an unidentified part'}, severity assessed as "
        f"{vision.aggregate_severity.value}, with damage geometry classified as '{physics.fracture_pattern}'."
    )
    facts = f"part={vision.aggregate_part}, issue={vision.aggregate_issue}, severity={vision.aggregate_severity.value}, fracture_pattern={physics.fracture_pattern}"
    return AgentVerdict(
        agent_name="Vision Expert",
        summary=_llm_summary("Vision Expert", facts, default),
        score=score,
        flags=[],
        raw={"aggregate_part": vision.aggregate_part, "aggregate_issue": vision.aggregate_issue, "severity": vision.aggregate_severity.value},
    )


def authenticity_expert_agent(authenticity: AuthenticityEngineOutput) -> AgentVerdict:
    score = authenticity.authenticity_score
    default = (
        f"Evidence authenticity score is {score}; "
        f"{'no significant manipulation signals detected' if not authenticity.flags else 'flagged signals: ' + ', '.join(f.value for f in authenticity.flags)}."
    )
    facts = f"authenticity_score={score}, flags={[f.value for f in authenticity.flags]}"
    return AgentVerdict(
        agent_name="Authenticity Expert",
        summary=_llm_summary("Authenticity Expert", facts, default),
        score=score,
        flags=authenticity.flags,
        raw={"authenticity_score": score},
    )


def evidence_expert_agent(sufficiency: SufficiencyEngineOutput) -> AgentVerdict:
    default = (
        f"Evidence coverage is {sufficiency.coverage_score * 100:.0f}%; "
        f"{'all required views present' if not sufficiency.missing_views else 'missing: ' + ', '.join(sufficiency.missing_views)}."
    )
    facts = f"coverage={sufficiency.coverage_score}, missing_views={sufficiency.missing_views}"
    return AgentVerdict(
        agent_name="Evidence Expert",
        summary=_llm_summary("Evidence Expert", facts, default),
        score=sufficiency.coverage_score,
        flags=sufficiency.flags,
        raw={"coverage_score": sufficiency.coverage_score, "missing_views": sufficiency.missing_views},
    )


def fraud_expert_agent(
    authenticity: AuthenticityEngineOutput,
    story: StoryConsistencyOutput,
    physics: PhysicsValidationOutput,
    fraud_network: FraudNetworkOutput,
    liveness: LivenessEngineOutput,
    temporal_geo: TemporalGeoOutput,
) -> AgentVerdict:
    """Fraud risk score: HIGHER = more suspicious (inverse semantics vs other
    agents, since this agent's whole purpose is to surface risk, not claim
    validity). Documented clearly so the Judge agent interprets it correctly."""
    risk = 0.0
    risk += (1.0 - authenticity.authenticity_score) * 0.25
    risk += (1.0 - story.consistency_score) * 0.20
    risk += (1.0 - physics.damage_authenticity_score) * 0.15
    risk += fraud_network.network_risk_score * 0.25
    if liveness.video_provided:
        risk += (1.0 - liveness.damage_liveness_score) * 0.10
    if temporal_geo.timestamp_before_policy or temporal_geo.geo_mismatch:
        risk += 0.15
    risk = round(min(risk, 1.0), 3)

    all_flags = list(dict.fromkeys(
        authenticity.flags + story.flags + physics.flags + fraud_network.flags
        + liveness.flags + temporal_geo.flags
    ))

    default = (
        f"Aggregate fraud risk score: {risk}. "
        f"{'Flagged indicators: ' + ', '.join(f.value for f in all_flags) if all_flags else 'No strong fraud indicators detected.'}"
    )
    facts = f"fraud_risk={risk}, flags={[f.value for f in all_flags]}"
    return AgentVerdict(
        agent_name="Fraud Expert",
        summary=_llm_summary("Fraud Expert", facts, default),
        score=risk,
        flags=all_flags,
        raw={"fraud_risk_score": risk},
    )


def history_expert_agent(user_risk: UserRiskOutput) -> AgentVerdict:
    # Trust score is inverse of risk score.
    trust_score = round(1.0 - user_risk.claimant_risk_score, 3)
    default = (
        f"Claimant has {user_risk.past_claim_count} past claims with a "
        f"{user_risk.rejection_rate * 100:.0f}% rejection rate; risk level assessed as {user_risk.risk_level.value}."
    )
    facts = f"past_claims={user_risk.past_claim_count}, rejection_rate={user_risk.rejection_rate}, risk_level={user_risk.risk_level.value}"
    return AgentVerdict(
        agent_name="History Expert",
        summary=_llm_summary("History Expert", facts, default),
        score=trust_score,
        flags=user_risk.flags,
        raw={"trust_score": trust_score, "risk_level": user_risk.risk_level.value},
    )


def ownership_expert_agent(ownership: OwnershipEngineOutput, possession: PossessionEngineOutput) -> AgentVerdict:
    combined = round(0.5 * ownership.ownership_score + 0.5 * possession.possession_score, 3)
    default = (
        f"Ownership confidence: {ownership.ownership_score}, possession confidence: {possession.possession_score}. "
        f"{'Identifiers matched claimant declaration.' if ownership.matches_user_provided_details else 'Some identifiers could not be confirmed.'}"
    )
    facts = f"ownership_score={ownership.ownership_score}, possession_score={possession.possession_score}, matches={ownership.matches_user_provided_details}"
    return AgentVerdict(
        agent_name="Ownership Expert",
        summary=_llm_summary("Ownership Expert", facts, default),
        score=combined,
        flags=list(dict.fromkeys(ownership.flags + possession.flags)),
        raw={"ownership_score": ownership.ownership_score, "possession_score": possession.possession_score},
    )


def run_all_agents(
    vision: VisionAnalysisOutput,
    authenticity: AuthenticityEngineOutput,
    sufficiency: SufficiencyEngineOutput,
    story: StoryConsistencyOutput,
    physics: PhysicsValidationOutput,
    fraud_network: FraudNetworkOutput,
    liveness: LivenessEngineOutput,
    temporal_geo: TemporalGeoOutput,
    user_risk: UserRiskOutput,
    ownership: OwnershipEngineOutput,
    possession: PossessionEngineOutput,
) -> List[AgentVerdict]:
    return [
        vision_expert_agent(vision, physics),
        authenticity_expert_agent(authenticity),
        evidence_expert_agent(sufficiency),
        fraud_expert_agent(authenticity, story, physics, fraud_network, liveness, temporal_geo),
        history_expert_agent(user_risk),
        ownership_expert_agent(ownership, possession),
    ]
