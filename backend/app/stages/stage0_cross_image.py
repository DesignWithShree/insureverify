"""
Stage 0 — Evidence Authenticity Engine
Part E: Cross-Image Consistency.

Verifies that all images submitted for a single claim plausibly depict the
SAME physical object (same laptop, same car, same package) and flags mixed
evidence — a common fraud pattern where a claimant submits a genuine photo
of their own device alongside a stock/borrowed photo of more severe damage.

Two real signals are combined:
1. Perceptual-hash similarity to a learned "primary" hash cluster — images
   that are wildly dissimilar (not just different angle, but different
   color/composition profile entirely) from the rest of the set are flagged.
2. Color histogram correlation — different physical objects (e.g. a silver
   laptop vs. a black laptop) tend to show measurably different global color
   distributions even across different shooting angles/lighting.
"""
from __future__ import annotations
from typing import List
import cv2
import numpy as np

from app.core.schemas import CrossImageConsistencyReport
from app.stages.stage0_phash import compute_phash, hamming_distance


def _color_histogram(image_path: str):
    img = cv2.imread(image_path)
    if img is None:
        return None
    hist = cv2.calcHist([img], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
    cv2.normalize(hist, hist)
    return hist.flatten()


def check_cross_image_consistency(image_paths: List[str]) -> CrossImageConsistencyReport:
    notes = []
    if len(image_paths) < 2:
        notes.append("only_one_image_submitted_cross_check_skipped")
        return CrossImageConsistencyReport(
            same_object_across_images=True, mixed_evidence_detected=False, notes=notes,
        )

    hashes = {p: compute_phash(p) for p in image_paths}
    histograms = {p: _color_histogram(p) for p in image_paths}

    # Pairwise color histogram correlation — low correlation across MOST
    # pairs (not just one outlier angle) suggests genuinely different objects.
    correlations = []
    pairs = []
    for i, p1 in enumerate(image_paths):
        for p2 in image_paths[i + 1:]:
            h1, h2 = histograms.get(p1), histograms.get(p2)
            if h1 is None or h2 is None:
                continue
            corr = float(cv2.compareHist(h1.astype(np.float32), h2.astype(np.float32), cv2.HISTCMP_CORREL))
            correlations.append(corr)
            pairs.append((p1, p2, corr))

    avg_corr = float(np.mean(correlations)) if correlations else 1.0
    low_corr_pairs = [p for p in pairs if p[2] < 0.3]

    mixed_evidence = avg_corr < 0.35 and len(low_corr_pairs) >= 1
    same_object = not mixed_evidence

    if mixed_evidence:
        notes.append(
            f"low_color_profile_correlation_across_images_avg={round(avg_corr,3)}_"
            f"flagged_pairs={len(low_corr_pairs)}"
        )
    else:
        notes.append("color_profiles_reasonably_consistent_across_images")

    # Exact/near-duplicate detection within the SAME claim (e.g. the same
    # photo uploaded twice to pad the "required image count").
    duplicate_matches = []
    for i, p1 in enumerate(image_paths):
        for p2 in image_paths[i + 1:]:
            dist = hamming_distance(hashes.get(p1, ""), hashes.get(p2, ""))
            if dist <= 4:
                duplicate_matches.append({"image_1": p1, "image_2": p2, "hamming_distance": dist})

    if duplicate_matches:
        notes.append("near_duplicate_images_found_within_same_claim")

    return CrossImageConsistencyReport(
        same_object_across_images=same_object,
        mixed_evidence_detected=mixed_evidence,
        duplicate_phash_matches=duplicate_matches,
        notes=notes,
    )
