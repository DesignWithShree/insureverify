"""
Stage 8 — Physics-Based Damage Validation Engine.

Real crack physics: impact fractures in brittle materials (glass, plastic,
laptop screens) propagate from a point of impact in branching patterns —
radiating lines that fork as they travel outward (this is well-documented
fracture mechanics, not a guess). Faked/drawn-on damage (e.g. a marker line
drawn on a screen, or a digitally pasted crack) tends to look different:
either too smooth/uniform, too perfectly straight, or randomly placed
without a consistent point of convergence.

This stage extracts crack-like line segments via Hough transform + contour
analysis, checks for line CONVERGENCE toward a common point of impact, and
scores branching complexity as a real geometric signal.
"""
from __future__ import annotations
from typing import List, Optional
import cv2
import numpy as np

from app.core.schemas import PhysicsValidationOutput, RiskFlag


def _detect_crack_lines(gray: np.ndarray):
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=30, minLineLength=15, maxLineGap=8)
    return lines


def _line_intersection(line1, line2) -> Optional[tuple]:
    x1, y1, x2, y2 = line1
    x3, y3, x4, y4 = line2
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-6:
        return None
    px = ((x1 - x2) * (x3 * y4 - y3 * x4) - (x3 - x4) * (x1 * y2 - y1 * x2)) / denom
    py = (y1 - y2) * (x3 * y4 - y3 * x4) / denom - (y3 - y4) * (x1 * y2 - y1 * x2) / denom if False else None
    # Simpler, numerically stable form:
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    px = x1 + t * (x2 - x1)
    py = y1 + t * (y2 - y1)
    return (px, py)


def analyze_fracture_pattern(image_path: str) -> PhysicsValidationOutput:
    notes = []
    img = cv2.imread(image_path)
    if img is None:
        return PhysicsValidationOutput(
            fracture_pattern="none", impact_point_detected=False,
            physically_plausible=True, damage_authenticity_score=0.5,
            notes=["could_not_load_image"],
        )

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    lines = _detect_crack_lines(gray)

    if lines is None or len(lines) < 3:
        notes.append("insufficient_line_structure_detected_for_fracture_analysis")
        return PhysicsValidationOutput(
            fracture_pattern="none", impact_point_detected=False,
            physically_plausible=True, damage_authenticity_score=0.5, notes=notes,
        )

    segments = [tuple(l[0]) for l in lines]

    # Convergence check: find pairwise intersection points of line segments
    # (extended) and see whether a meaningful cluster of intersections falls
    # within the image bounds and close together — that cluster is the
    # candidate "impact point" a real fracture would radiate from.
    intersections = []
    for i in range(len(segments)):
        for j in range(i + 1, min(i + 8, len(segments))):  # cap pairwise checks for speed
            pt = _line_intersection(segments[i], segments[j])
            if pt and -w * 0.2 <= pt[0] <= w * 1.2 and -h * 0.2 <= pt[1] <= h * 1.2:
                intersections.append(pt)

    impact_point_detected = False
    cluster_tightness = 0.0
    if len(intersections) >= 3:
        pts = np.array(intersections)
        # Use median as a robust center estimate, then measure how tightly
        # intersections cluster around it relative to image diagonal.
        center = np.median(pts, axis=0)
        dists = np.linalg.norm(pts - center, axis=1)
        diag = np.sqrt(h ** 2 + w ** 2)
        tight_fraction = float(np.mean(dists < diag * 0.15))
        cluster_tightness = tight_fraction
        impact_point_detected = tight_fraction > 0.35
        if impact_point_detected:
            notes.append("line_segments_converge_toward_a_common_impact_point_consistent_with_real_fracture")
        else:
            notes.append("line_segments_do_not_converge_to_a_common_point_pattern_appears_dispersed")
    else:
        notes.append("too_few_line_intersections_to_assess_convergence")

    # Branching complexity: real fractures have varied line angles (forking),
    # whereas drawn/faked damage is often dominated by 1-2 near-parallel
    # straight strokes.
    angles = [float(np.arctan2(s[3] - s[1], s[2] - s[0])) for s in segments]
    angle_std = float(np.std(angles))
    branching_complexity = min(angle_std / 1.2, 1.0)  # normalize roughly to 0-1

    if branching_complexity < 0.25:
        notes.append("lines_are_unusually_uniform_in_direction_few_near_parallel_strokes_atypical_of_real_fracture_branching")
        fracture_pattern = "random_lines" if not impact_point_detected else "radial"
    elif impact_point_detected:
        fracture_pattern = "branching"
        notes.append("varied_line_angles_consistent_with_branching_fracture_propagation")
    else:
        fracture_pattern = "random_lines"

    # Authenticity score combines convergence + branching complexity. Both
    # being low strongly suggests a non-physical (drawn/pasted) crack.
    score = 0.5 * cluster_tightness + 0.5 * branching_complexity
    physically_plausible = score > 0.3

    flags = []
    if not physically_plausible:
        flags.append(RiskFlag.photoshopped_damage)

    return PhysicsValidationOutput(
        fracture_pattern=fracture_pattern,
        impact_point_detected=impact_point_detected,
        physically_plausible=physically_plausible,
        damage_authenticity_score=round(float(np.clip(score, 0, 1)), 3),
        notes=notes,
        flags=flags,
    )
