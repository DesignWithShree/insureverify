"""
Stage 7 — Story Consistency Engine.

Cross-checks the claimant's stated cause (Stage 6 output) against what was
OBJECTIVELY observed in the images (Stage 5 output, which never saw the
claim text). A mismatch here — e.g. claimed "fell and screen cracked" but
the VLM independently observed water damage with no fracture — is one of
the clearest fraud/misrepresentation signals in the whole pipeline, because
the two signals were generated completely independently of each other.
"""
from __future__ import annotations
import json
import re

from app.core.schemas import (
    StoryConsistencyOutput, ClaimUnderstandingOutput, VisionAnalysisOutput, RiskFlag,
)
from app.core.taxonomy import EXPECTED_DAMAGE_PATTERNS
from app.utils.ollama_client import query_text_model, is_ollama_available

STORY_CONSISTENCY_SYSTEM_PROMPT = """You are a careful insurance claims investigator
assessing whether a claimed cause of damage is physically consistent with what was
independently observed in evidence photos. Be skeptical but fair — partial matches are
common and not automatically fraud. Respond ONLY with JSON, no other text."""

STORY_CONSISTENCY_PROMPT_TEMPLATE = """Claimed cause: {cause}
Claimed issue: {claimed_issue}
Claimed part: {claimed_part}

Independently observed (from photos, the model did NOT see the claim text):
Observed issue: {observed_issue}
Observed part: {observed_part}
Observed severity: {observed_severity}
Image descriptions: {descriptions}

Expected damage pattern for this cause: {expected_pattern}

Assess consistency. Respond ONLY with JSON:
{{
  "is_consistent": <true|false>,
  "consistency_score": <float 0 to 1>,
  "reasoning": "<one or two sentences explaining your assessment>"
}}"""


def _rule_based_consistency(
    claim_understanding: ClaimUnderstandingOutput, vision: VisionAnalysisOutput, claim_object: str,
) -> StoryConsistencyOutput:
    cause = claim_understanding.claimed_cause or "unknown"
    expected_pattern = EXPECTED_DAMAGE_PATTERNS.get(cause, {}).get(claim_object, "unspecified")

    observed_issue = vision.aggregate_issue
    claimed_issue = claim_understanding.claimed_issue

    part_match = (
        claim_understanding.claimed_part and vision.aggregate_part
        and claim_understanding.claimed_part == vision.aggregate_part
    )
    issue_match = claimed_issue and observed_issue and claimed_issue == observed_issue

    # Special-case the clearest mismatch the spec calls out explicitly:
    # claimed mechanical cause (fall/collision) but observed issue is water
    # damage with no fracture-type issue, or vice versa.
    mechanical_causes = {"fall", "collision", "theft_attempt", "shipping_mishandling"}
    if cause in mechanical_causes and observed_issue == "water_damage":
        return StoryConsistencyOutput(
            expected_damage_pattern=expected_pattern,
            observed_damage_pattern=f"part={vision.aggregate_part}, issue={observed_issue}",
            is_consistent=False,
            consistency_score=0.1,
            reasoning=(
                f"Claimant described a {cause.replace('_', ' ')} incident, which typically "
                "produces mechanical/impact damage, but the evidence independently shows "
                "water damage with no fracture pattern. These are not consistent."
            ),
            flags=[RiskFlag.claim_mismatch],
        )

    if cause == "water_spill" and observed_issue and observed_issue != "water_damage":
        return StoryConsistencyOutput(
            expected_damage_pattern=expected_pattern,
            observed_damage_pattern=f"part={vision.aggregate_part}, issue={observed_issue}",
            is_consistent=False,
            consistency_score=0.15,
            reasoning=(
                "Claimant described liquid/water damage, but the evidence independently "
                f"shows a different issue ('{observed_issue}') with no water-damage signature."
            ),
            flags=[RiskFlag.claim_mismatch],
        )

    if not observed_issue and not claimed_issue:
        score, consistent, reasoning = 0.5, True, "Insufficient detail in both claim and observation to assess consistency strongly either way."
        flags = []
    elif issue_match and (part_match or not claim_understanding.claimed_part):
        score, consistent, reasoning = 0.9, True, "Observed damage issue and part align with the claimant's description."
        flags = []
    elif issue_match and not part_match:
        score, consistent, reasoning = 0.6, True, "Observed issue type matches the claim, though the specific part is uncertain or differs slightly."
        flags = []
    elif observed_issue and claimed_issue and observed_issue != claimed_issue:
        score, consistent, reasoning = 0.25, False, f"Claimant described '{claimed_issue}' but evidence independently shows '{observed_issue}'."
        flags = [RiskFlag.claim_mismatch]
    else:
        score, consistent, reasoning = 0.5, True, "Partial information available; no strong contradiction detected, but also no strong confirmation."
        flags = []

    return StoryConsistencyOutput(
        expected_damage_pattern=expected_pattern,
        observed_damage_pattern=f"part={vision.aggregate_part}, issue={observed_issue}",
        is_consistent=consistent,
        consistency_score=score,
        reasoning=reasoning,
        flags=flags,
    )


def run_story_consistency_engine(
    claim_understanding: ClaimUnderstandingOutput, vision: VisionAnalysisOutput, claim_object: str,
) -> StoryConsistencyOutput:
    rule_based = _rule_based_consistency(claim_understanding, vision, claim_object)

    if not is_ollama_available():
        return rule_based

    cause = claim_understanding.claimed_cause or "unknown"
    expected_pattern = EXPECTED_DAMAGE_PATTERNS.get(cause, {}).get(claim_object, "unspecified")
    descriptions = " | ".join(o.objective_description for o in vision.observations)[:800]

    prompt = STORY_CONSISTENCY_PROMPT_TEMPLATE.format(
        cause=cause,
        claimed_issue=claim_understanding.claimed_issue or "unspecified",
        claimed_part=claim_understanding.claimed_part or "unspecified",
        observed_issue=vision.aggregate_issue or "unspecified",
        observed_part=vision.aggregate_part or "unspecified",
        observed_severity=vision.aggregate_severity.value,
        descriptions=descriptions,
        expected_pattern=expected_pattern,
    )
    raw = query_text_model(prompt, system=STORY_CONSISTENCY_SYSTEM_PROMPT, json_mode=True)

    try:
        parsed = json.loads(raw)
    except Exception:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        parsed = json.loads(match.group(0)) if match else None

    if not parsed:
        return rule_based

    # The LLM result supplements but does not override a clear rule-based
    # contradiction (e.g. the water-damage-vs-mechanical-cause case) — those
    # are deterministic facts, not matters of LLM judgement.
    if rule_based.flags:
        return rule_based

    return StoryConsistencyOutput(
        expected_damage_pattern=expected_pattern,
        observed_damage_pattern=rule_based.observed_damage_pattern,
        is_consistent=bool(parsed.get("is_consistent", rule_based.is_consistent)),
        consistency_score=float(parsed.get("consistency_score", rule_based.consistency_score)),
        reasoning=str(parsed.get("reasoning", rule_based.reasoning)),
        flags=[] if parsed.get("is_consistent", True) else [RiskFlag.claim_mismatch],
    )
