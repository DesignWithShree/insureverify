"""
Stage 6 — Claim Understanding Engine.

Extracts structured fields (object, part, issue, cause) from the claimant's
free-text description, e.g. "My laptop screen cracked after falling."
Primary path uses llama3 (via Ollama) for robust NLU; falls back to
keyword/regex matching against the taxonomy if Ollama is unavailable, so the
pipeline degrades gracefully rather than failing outright.
"""
from __future__ import annotations
import json
import re

from app.core.schemas import ClaimUnderstandingOutput
from app.core.taxonomy import OBJECT_PARTS, OBJECT_ISSUES
from app.utils.ollama_client import query_text_model, is_ollama_available

CAUSE_KEYWORDS = {
    "fall": ["fell", "fall", "dropped", "drop"],
    "collision": ["hit", "collided", "collision", "crashed", "crash", "bumped", "accident"],
    "water_spill": ["spilled", "spill", "water", "rain", "flood", "liquid"],
    "theft_attempt": ["theft", "stolen", "broke in", "break-in", "burglar", "pry"],
    "shipping_mishandling": ["shipping", "courier", "delivery", "transit", "mishandled"],
}

CLAIM_UNDERSTANDING_SYSTEM_PROMPT = """You extract structured facts from insurance claim
descriptions. You only extract what is explicitly stated or very strongly implied — never invent
details. Respond ONLY with JSON, no other text."""

CLAIM_UNDERSTANDING_PROMPT_TEMPLATE = """Claim text: "{claim_text}"

Extract the following as JSON:
{{
  "object": "<car|laptop|package|unknown>",
  "part": "<specific part if mentioned or strongly implied, else 'unknown'>",
  "issue": "<specific issue/damage type if mentioned, else 'unknown'>",
  "cause": "<one of: fall, collision, water_spill, theft_attempt, shipping_mishandling, unknown>"
}}"""


def _regex_fallback(claim_text: str, claim_object: str) -> ClaimUnderstandingOutput:
    text_lower = claim_text.lower()

    detected_part = None
    for part in OBJECT_PARTS.get(claim_object, []):
        if part.replace("_", " ") in text_lower:
            detected_part = part
            break

    detected_issue = None
    for issue in OBJECT_ISSUES.get(claim_object, []):
        if issue.replace("_", " ") in text_lower:
            detected_issue = issue
            break

    detected_cause = "unknown"
    for cause, keywords in CAUSE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            detected_cause = cause
            break

    return ClaimUnderstandingOutput(
        claimed_object=claim_object,
        claimed_part=detected_part,
        claimed_issue=detected_issue,
        claimed_cause=detected_cause,
        raw_text=claim_text,
    )


def run_claim_understanding(claim_text: str, claim_object: str) -> ClaimUnderstandingOutput:
    if not is_ollama_available():
        return _regex_fallback(claim_text, claim_object)

    prompt = CLAIM_UNDERSTANDING_PROMPT_TEMPLATE.format(claim_text=claim_text)
    raw = query_text_model(prompt, system=CLAIM_UNDERSTANDING_SYSTEM_PROMPT, json_mode=True)

    try:
        parsed = json.loads(raw)
    except Exception:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        parsed = json.loads(match.group(0)) if match else None

    if not parsed:
        return _regex_fallback(claim_text, claim_object)

    def _clean(v):
        return None if v in (None, "unknown", "") else v

    return ClaimUnderstandingOutput(
        claimed_object=_clean(parsed.get("object")) or claim_object,
        claimed_part=_clean(parsed.get("part")),
        claimed_issue=_clean(parsed.get("issue")),
        claimed_cause=_clean(parsed.get("cause")) or "unknown",
        raw_text=claim_text,
    )
