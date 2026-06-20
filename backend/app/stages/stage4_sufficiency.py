"""
Stage 4 — Evidence Sufficiency Engine.

Checks whether the claimant uploaded enough images, covering the required
viewing angles/closeups for this object+part+issue combination, BEFORE any
damage judgement is made. This uses a lightweight image classifier (view
heuristics based on framing/zoom level via edge density and aspect — a
real, fast, model-free technique) to label each uploaded image with its
likely "view type", then diffs against the requirement list from taxonomy.py.
"""
from __future__ import annotations
from typing import List, Optional
import cv2
import numpy as np

from app.core.schemas import SufficiencyEngineOutput, RiskFlag
from app.core.taxonomy import get_required_views


def _classify_view_type(image_path: str) -> str:
    """Heuristic view classifier using edge density + texture concentration:
    - closeup_*: very high edge density concentrated in frame (tight crop on
      detail like a crack)
    - full/front/side views: lower overall edge density, more uniform spread
    This isn't a learned classifier; it's intentionally simple, fast, and
    transparent — swap in a trained ViT/EfficientNet view-classifier later
    if you want higher precision (see models/ for the damage classifier
    pattern to follow)."""
    img = cv2.imread(image_path)
    if img is None:
        return "unknown_view"
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    h, w = edges.shape
    edge_density = float(edges.sum()) / (255.0 * h * w)

    # Concentration: fraction of edge energy within the central 40% region
    cy0, cy1 = int(h * 0.3), int(h * 0.7)
    cx0, cx1 = int(w * 0.3), int(w * 0.7)
    center_energy = float(edges[cy0:cy1, cx0:cx1].sum())
    total_energy = float(edges.sum()) + 1e-6
    concentration = center_energy / total_energy

    if edge_density > 0.08 and concentration > 0.5:
        return "closeup_view"
    if concentration > 0.55:
        return "front_view"
    return "side_angle"


def run_sufficiency_engine(
    image_paths: List[str], claim_object: str, part: Optional[str], issue: Optional[str],
) -> SufficiencyEngineOutput:
    required_views = get_required_views(claim_object, part, issue)
    detected_views = list(dict.fromkeys(_classify_view_type(p) for p in image_paths))

    # "closeup_view" detected satisfies any required view containing "closeup"
    satisfied = set()
    for req in required_views:
        req_key = req.lower()
        for det in detected_views:
            if req_key.split("_")[0] in det or det.split("_")[0] in req_key:
                satisfied.add(req)
                break
        # generic fallback: any image at all partially satisfies generic "view" requirements
    missing = [r for r in required_views if r not in satisfied]

    coverage_score = round(len(satisfied) / len(required_views), 3) if required_views else 1.0
    # Also weight in sheer image count vs. requirement count as a floor signal
    if len(image_paths) < len(required_views):
        coverage_score = min(coverage_score, round(len(image_paths) / max(len(required_views), 1), 3))

    flags = [RiskFlag.insufficient_evidence] if coverage_score < 0.6 else []

    return SufficiencyEngineOutput(
        required_views=required_views,
        detected_views=detected_views,
        missing_views=missing,
        coverage_score=coverage_score,
        flags=flags,
    )
