"""
CSV export layer.

Maps InsureVerify's internal pipeline outputs (ClaimRecord + FinalVerdict)
onto a flat, standardized output.csv schema:

    user_id, image_paths, user_claim, claim_object,
    evidence_standard_met, evidence_standard_met_reason, risk_flags,
    issue_type, object_part, claim_status, claim_status_justification,
    supporting_image_ids, valid_image, severity

This is a pure presentation/export layer — it does not change or
re-compute any pipeline logic. Every value here is read directly from
already-computed stage outputs (Stage 0 authenticity, Stage 4 sufficiency,
Stage 5 vision, the Judge's FinalVerdict). Three fields don't have a
1:1 source field in the internal schema and need a small derivation,
documented inline below:

  - evidence_standard_met / evidence_standard_met_reason
        derived from Stage 4 (Evidence Sufficiency) coverage_score + missing_views
  - supporting_image_ids
        derived by re-deriving short "img_N" IDs (in upload order) for
        whichever images Stage 0 scored as reasonably trustworthy
        (image_authenticity_score above threshold), since the chain of
        evidence references full file paths, not short IDs
  - valid_image
        derived from Stage 0's aggregate authenticity_score
"""
from __future__ import annotations
import csv
import io
from pathlib import Path
from typing import List, Optional

from app.core.schemas import ClaimRecord, FinalVerdict

CSV_COLUMNS = [
    "user_id",
    "image_paths",
    "user_claim",
    "claim_object",
    "evidence_standard_met",
    "evidence_standard_met_reason",
    "risk_flags",
    "issue_type",
    "object_part",
    "claim_status",
    "claim_status_justification",
    "supporting_image_ids",
    "valid_image",
    "severity",
]

# Thresholds used only for the two derived boolean fields below. These are
# intentionally the same thresholds already used elsewhere in the pipeline
# (sufficiency/authenticity scoring) — no new judgement logic is introduced
# here, just a boolean readout of scores the pipeline already computed.
EVIDENCE_STANDARD_MET_THRESHOLD = 0.6   # matches Stage 4's own insufficient-evidence flag threshold
VALID_IMAGE_THRESHOLD = 0.4             # below this, Stage 0 already flags the image as untrustworthy


def _short_image_ids(image_paths: List[str]) -> List[str]:
    """Assigns sequential img_1, img_2, ... IDs in upload order. This gives
    a stable, human-readable ID per image without depending on the
    underlying filename (which is a UUID, not meaningful on its own)."""
    return [f"img_{i+1}" for i in range(len(image_paths))]


def _evidence_standard_fields(verdict: Optional[FinalVerdict]) -> tuple[str, str]:
    if verdict is None:
        return "false", "Claim has not been verified yet."

    # Reconstruct the sufficiency-driven reason from what's already on the
    # verdict: evidence_coverage_score plus, if available, which risk flag
    # was raised for insufficient evidence.
    coverage = verdict.evidence_coverage_score
    met = coverage >= EVIDENCE_STANDARD_MET_THRESHOLD
    if met:
        reason = f"Evidence coverage score of {round(coverage * 100)}% meets the required threshold for this claim type."
    else:
        reason = f"Evidence coverage score of {round(coverage * 100)}% falls below the required threshold; required viewing angles are missing."
    return ("true" if met else "false"), reason


def _supporting_image_ids(claim: ClaimRecord, verdict: Optional[FinalVerdict]) -> str:
    if verdict is None or not claim.image_paths:
        return "none"

    ids = _short_image_ids(claim.image_paths)
    id_by_path = dict(zip(claim.image_paths, ids))

    supporting = [
        id_by_path[pi.image_path]
        for pi in verdict.per_image_summary
        if pi.image_path in id_by_path and pi.image_authenticity_score >= VALID_IMAGE_THRESHOLD
    ]
    # Fallback: if per_image_summary is empty (e.g. no images were scored
    # for some reason) but the claim is otherwise supported, don't silently
    # claim zero support — fall back to "all submitted images" rather than
    # fabricating a more specific answer we don't have evidence for.
    if not supporting and verdict.claim_status.value == "supported":
        supporting = ids

    return ";".join(supporting) if supporting else "none"


def _valid_image(verdict: Optional[FinalVerdict]) -> str:
    if verdict is None:
        return "false"
    return "true" if verdict.authenticity_score >= VALID_IMAGE_THRESHOLD else "false"


def _risk_flags(verdict: Optional[FinalVerdict]) -> str:
    if verdict is None or not verdict.risk_flags:
        return "none"
    return ";".join(f.value for f in verdict.risk_flags)


def claim_to_row(claim: ClaimRecord) -> dict:
    """Maps a single ClaimRecord (+ its FinalVerdict, if computed) to one
    output.csv row as a dict keyed by CSV_COLUMNS."""
    verdict = claim.verdict
    evidence_met, evidence_reason = _evidence_standard_fields(verdict)

    return {
        "user_id": claim.submission.user_id,
        "image_paths": ";".join(claim.image_paths),
        "user_claim": claim.submission.user_claim,
        "claim_object": claim.submission.claim_object.value,
        "evidence_standard_met": evidence_met,
        "evidence_standard_met_reason": evidence_reason,
        "risk_flags": _risk_flags(verdict),
        "issue_type": (verdict.chain_of_evidence and _issue_type(verdict)) or "unknown" if verdict else "unknown",
        "object_part": _object_part(verdict) if verdict else "unknown",
        "claim_status": verdict.claim_status.value if verdict else "not_enough_information",
        "claim_status_justification": verdict.final_justification if verdict else "Claim has not been verified yet.",
        "supporting_image_ids": _supporting_image_ids(claim, verdict),
        "valid_image": _valid_image(verdict),
        "severity": verdict.severity.value if verdict else "unknown",
    }


def _issue_type(verdict: FinalVerdict) -> str:
    # aggregate_issue isn't stored directly on FinalVerdict (it lives on the
    # Vision stage output, which isn't persisted standalone) — but the
    # Vision Expert agent's raw payload carries it through unchanged, so we
    # read it from there rather than recomputing anything.
    vision_agent = next((a for a in verdict.agent_verdicts if a.agent_name == "Vision Expert"), None)
    if vision_agent and vision_agent.raw.get("aggregate_issue"):
        return vision_agent.raw["aggregate_issue"]
    return "unknown"


def _object_part(verdict: FinalVerdict) -> str:
    vision_agent = next((a for a in verdict.agent_verdicts if a.agent_name == "Vision Expert"), None)
    if vision_agent and vision_agent.raw.get("aggregate_part"):
        return vision_agent.raw["aggregate_part"]
    return "unknown"


def claims_to_csv_string(claims: List[ClaimRecord]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_ALL)
    writer.writeheader()
    for claim in claims:
        writer.writerow(claim_to_row(claim))
    return buffer.getvalue()


def write_claims_csv(claims: List[ClaimRecord], output_path: str) -> None:
    csv_string = claims_to_csv_string(claims)
    Path(output_path).write_text(csv_string, encoding="utf-8")


def append_claim_to_csv(claim: ClaimRecord, output_path: str) -> None:
    """Appends a single claim's row to output_path, writing the header first
    if the file doesn't exist yet. Used for the 'live, incremental' export
    mode — called automatically right after each claim is verified."""
    path = Path(output_path)
    file_exists = path.exists() and path.stat().st_size > 0

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_ALL)
        if not file_exists:
            writer.writeheader()
        writer.writerow(claim_to_row(claim))
