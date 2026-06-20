"""
Stage 0 — Evidence Authenticity Engine (Orchestrator)

Runs BEFORE damage detection, exactly as specified: verifies that the
evidence itself can be trusted before any damage claim is evaluated on it.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from app.core.schemas import (
    AuthenticityEngineOutput, PerImageAuthenticity, RiskFlag,
)
from app.stages.stage0_metadata import extract_metadata
from app.stages.stage0_ela import compute_ela
from app.stages.stage0_visual_forensics import analyze_reflection_consistency, detect_ai_generated
from app.stages.stage0_phash import compute_phash
from app.stages.stage0_cross_image import check_cross_image_consistency
from app.stages.stage0_vlm_edit_check import check_for_semantic_edit_artifacts

MAX_PARALLEL_FORENSIC_CALLS = 4


def _per_image_score(
    metadata_suspicious: bool, ela_score: float, ai_prob: float, lighting_score: float,
    vlm_edit_result: dict,
) -> float:
    """Weighted aggregate — metadata issues are a softer signal (many
    legitimate phones strip EXIF via messaging apps), ELA and AI-generation
    probability are stronger signals of deliberate manipulation. The VLM
    semantic check, when available, is weighted similarly to the pixel-stat
    signals since it catches a genuinely different failure mode (see
    stage0_vlm_edit_check.py) rather than being redundant with them."""
    score = 1.0
    if metadata_suspicious:
        score -= 0.10
    score -= 0.30 * ela_score
    score -= 0.30 * ai_prob
    score -= 0.10 * (1.0 - lighting_score)
    if vlm_edit_result.get("available") and vlm_edit_result.get("looks_edited"):
        score -= 0.30 * vlm_edit_result.get("confidence", 0.5)
    return max(0.0, min(1.0, score))


def _analyze_one_image(path: str) -> tuple:
    metadata = extract_metadata(path)
    ela = compute_ela(path)
    ai_report = detect_ai_generated(path)
    reflection = analyze_reflection_consistency(path)
    phash = compute_phash(path)
    vlm_edit_result = check_for_semantic_edit_artifacts(path)

    if vlm_edit_result.get("available") and vlm_edit_result.get("looks_edited"):
        ai_report.signals.append(
            f"vlm_flagged_possible_digital_edit_confidence_{round(vlm_edit_result['confidence'], 2)}"
            + (f"_reason:{vlm_edit_result['description']}" if vlm_edit_result["description"] else "")
        )

    score = _per_image_score(
        metadata.suspicious_metadata, ela.manipulation_score,
        ai_report.ai_generation_probability, reflection.lighting_consistency_score,
        vlm_edit_result,
    )

    per_image_result = PerImageAuthenticity(
        image_path=path, metadata=metadata, ela=ela, ai_generated=ai_report,
        reflection=reflection, phash=phash, image_authenticity_score=round(score, 3),
    )
    return per_image_result, vlm_edit_result


def run_authenticity_engine(image_paths: List[str]) -> AuthenticityEngineOutput:
    if not image_paths:
        per_image, vlm_results = [], []
    else:
        # The classical CV checks (metadata/ELA/AI-stats/reflection/phash)
        # are fast, but the new VLM edit check is a real Ollama call (slow
        # on CPU) — running images concurrently keeps this stage's total
        # latency close to a single image's worth of time rather than N times
        # that, same rationale as Stage 5's vision analysis parallelization.
        results = [None] * len(image_paths)
        with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_FORENSIC_CALLS, len(image_paths))) as pool:
            future_to_idx = {pool.submit(_analyze_one_image, p): i for i, p in enumerate(image_paths)}
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                results[idx] = future.result()
        per_image = [r[0] for r in results]
        vlm_results = [r[1] for r in results]

    cross_image = check_cross_image_consistency(image_paths)

    flags: List[RiskFlag] = []
    if any(p.ai_generated.ai_generation_probability > 0.55 for p in per_image):
        flags.append(RiskFlag.ai_generated_image)
    if any(p.ela.manipulation_score > 0.4 for p in per_image):
        flags.append(RiskFlag.photoshopped_damage)
    if any(p.metadata.suspicious_metadata and "ai_generation_software_detected" in str(p.metadata.metadata_flags) for p in per_image):
        flags.append(RiskFlag.ai_generated_image)
    if any("editing_software_detected" in f for p in per_image for f in p.metadata.metadata_flags):
        flags.append(RiskFlag.manipulated_metadata)
    if any(r.get("available") and r.get("looks_edited") and r.get("confidence", 0) > 0.5 for r in vlm_results):
        flags.append(RiskFlag.photoshopped_damage)
    if cross_image.mixed_evidence_detected:
        flags.append(RiskFlag.mixed_evidence_multiple_devices)
    if cross_image.duplicate_phash_matches:
        flags.append(RiskFlag.reused_claim_photo)

    aggregate_score = round(sum(p.image_authenticity_score for p in per_image) / len(per_image), 3) if per_image else 0.0
    if cross_image.mixed_evidence_detected:
        aggregate_score = round(aggregate_score * 0.7, 3)

    return AuthenticityEngineOutput(
        per_image=per_image,
        cross_image=cross_image,
        authenticity_score=aggregate_score,
        flags=list(dict.fromkeys(flags)),  # dedupe, preserve order
    )
