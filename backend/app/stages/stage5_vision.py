"""
Stage 5 — Vision Language Analysis Engine.

CRITICAL DESIGN RULE: the VLM must never see the user's claim text. It is
prompted to describe ONLY what it observes in the image, independently. This
is what allows Stage 7 (Story Consistency) to be a genuine cross-check rather
than the model simply parroting back the claim it was told to look for.

Two layers:
1. Primary: local llava (via Ollama) for natural-language objective
   description + structured part/issue/severity extraction.
2. Fallback / supplement: classical CV damage heuristics (edge density,
   contour irregularity, color-anomaly detection) so the pipeline still
   produces a real (if coarser) signal even if Ollama isn't running, and so
   Stage 8 (physics validation) has independent geometric data to check
   against the VLM's claim.
"""
from __future__ import annotations
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
import cv2
import numpy as np

from app.core.schemas import VisionAnalysisOutput, VisionObservation, Severity
from app.core.taxonomy import OBJECT_PARTS, OBJECT_ISSUES
from app.utils.ollama_client import query_vision_model, is_ollama_available

MAX_PARALLEL_VISION_CALLS = 4  # caps concurrent llava calls; raise if your machine has GPU headroom

OBJECTIVE_DESCRIPTION_PROMPT = """You are examining a photo submitted as insurance evidence.
Describe ONLY what you literally observe in the image. Do NOT speculate about
cause, intent, or any backstory. Do not assume anything you were not told.

Respond ONLY in this exact JSON structure, no other text:
{{
  "description": "<one or two objective sentences describing what is visible>",
  "object_type": "<car|laptop|package|unknown>",
  "part": "<specific part visible, choose from: {parts}, or 'unknown'>",
  "issue": "<specific issue visible, choose from: {issues}, or 'none'>",
  "severity": "<none|low|medium|high|unknown>",
  "confidence": <float 0 to 1>
}}"""


def _cv_fallback_observation(image_path: str) -> VisionObservation:
    """Classical-CV coarse damage heuristic, used when Ollama/llava is
    unavailable or returns an unparseable response. Looks for irregular
    high-contrast contours (cracks, dents create sharp local discontinuities)
    and estimates rough severity from affected area fraction."""
    img = cv2.imread(image_path)
    if img is None:
        return VisionObservation(
            image_path=image_path, objective_description="Could not load image.",
            severity=Severity.unknown, confidence=0.0,
        )
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 80, 180)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = gray.shape
    total_area = h * w
    damage_area = sum(cv2.contourArea(c) for c in contours if cv2.contourArea(c) > 50)
    area_fraction = damage_area / total_area if total_area else 0.0

    if area_fraction < 0.01:
        severity = Severity.low
        desc = "Minor surface irregularity detected; no large-scale structural damage visible."
    elif area_fraction < 0.05:
        severity = Severity.medium
        desc = "Moderate visible damage pattern detected covering a noticeable portion of the frame."
    else:
        severity = Severity.high
        desc = "Extensive irregular damage pattern detected covering a large portion of the frame."

    return VisionObservation(
        image_path=image_path,
        objective_description=desc + " (classical-CV fallback analysis; Ollama/llava unavailable)",
        detected_object=None,
        detected_part=None,
        detected_issue=None,
        severity=severity,
        confidence=0.35,  # intentionally low confidence — this is a coarse fallback
    )


def _parse_llava_json(raw: str) -> Optional[dict]:
    try:
        return json.loads(raw)
    except Exception:
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    return None


def _analyze_single_image(image_path: str, claim_object: str) -> VisionObservation:
    if not is_ollama_available():
        return _cv_fallback_observation(image_path)

    parts = ", ".join(OBJECT_PARTS.get(claim_object, []))
    issues = ", ".join(OBJECT_ISSUES.get(claim_object, []))
    prompt = OBJECTIVE_DESCRIPTION_PROMPT.format(parts=parts, issues=issues)

    raw = query_vision_model(image_path, prompt, json_mode=True)
    parsed = _parse_llava_json(raw)

    if not parsed:
        fallback = _cv_fallback_observation(image_path)
        fallback.objective_description += " (llava response unparseable, used CV fallback)"
        return fallback

    severity_str = str(parsed.get("severity", "unknown")).lower()
    try:
        severity = Severity(severity_str)
    except ValueError:
        severity = Severity.unknown

    issue = parsed.get("issue")
    if issue in (None, "none", ""):
        issue = None
    part = parsed.get("part")
    if part in (None, "unknown", ""):
        part = None

    return VisionObservation(
        image_path=image_path,
        objective_description=str(parsed.get("description", "")),
        detected_object=parsed.get("object_type") if parsed.get("object_type") != "unknown" else None,
        detected_part=part,
        detected_issue=issue,
        severity=severity,
        confidence=float(parsed.get("confidence", 0.5)),
    )


def run_vision_analysis(image_paths: List[str], claim_object: str) -> VisionAnalysisOutput:
    if not image_paths:
        observations = []
    elif not is_ollama_available():
        # No Ollama -> CV fallback is fast (<1s/image), no need for threading.
        observations = [_cv_fallback_observation(p) for p in image_paths]
    else:
        # llava calls are slow (seconds-to-tens-of-seconds each on CPU) and
        # independent per image, so run them concurrently rather than one
        # after another — this is the single biggest latency win available
        # without changing models.
        observations = [None] * len(image_paths)
        with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_VISION_CALLS, len(image_paths))) as pool:
            future_to_idx = {
                pool.submit(_analyze_single_image, p, claim_object): i
                for i, p in enumerate(image_paths)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    observations[idx] = future.result()
                except Exception:
                    observations[idx] = _cv_fallback_observation(image_paths[idx])

    # Aggregate: majority vote on part/issue, max severity observed.
    parts = [o.detected_part for o in observations if o.detected_part]
    issues = [o.detected_issue for o in observations if o.detected_issue]
    severities = [o.severity for o in observations]

    severity_order = [Severity.none, Severity.low, Severity.medium, Severity.high]
    known_severities = [s for s in severities if s in severity_order]
    aggregate_severity = max(known_severities, key=lambda s: severity_order.index(s)) if known_severities else Severity.unknown

    aggregate_part = max(set(parts), key=parts.count) if parts else None
    aggregate_issue = max(set(issues), key=issues.count) if issues else None

    return VisionAnalysisOutput(
        observations=observations,
        aggregate_part=aggregate_part,
        aggregate_issue=aggregate_issue,
        aggregate_severity=aggregate_severity,
    )
