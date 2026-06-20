"""
Stage 0 — Evidence Authenticity Engine
Part D: Reflection/Lighting Consistency + AI-Generated Image Heuristics.

Two real, classical-CV techniques are implemented here (no external network
calls, no paid API):

1. Lighting/shadow consistency: estimates dominant light direction from
   gradient analysis across image regions and checks whether shading is
   consistent across the frame — a known technique for detecting composited
   images (different regions lit from "different suns").

2. AI-generation heuristics: real, well-documented statistical artifacts of
   diffusion-model output — unnaturally smooth/low-frequency noise floor,
   suspiciously perfect symmetry, and FFT spectral signatures that differ
   from camera sensor noise. This is a heuristic detector, not a trained
   classifier — it is deliberately conservative (low false-positive bias)
   and is clearly surfaced as a probability, not a certainty, in the output.
"""
from __future__ import annotations
import numpy as np
import cv2

from app.core.schemas import ReflectionConsistencyReport, AIGeneratedReport


def analyze_reflection_consistency(image_path: str) -> ReflectionConsistencyReport:
    notes = []
    img = cv2.imread(image_path)
    if img is None:
        return ReflectionConsistencyReport(
            lighting_consistency_score=0.5, shadow_consistency_score=0.5,
            notes=["could_not_load_image"],
        )

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # Split into quadrants and estimate the dominant gradient direction in
    # each (a rough proxy for local light direction via image gradients).
    quadrants = [
        gray[0:h // 2, 0:w // 2],
        gray[0:h // 2, w // 2:w],
        gray[h // 2:h, 0:w // 2],
        gray[h // 2:h, w // 2:w],
    ]
    directions = []
    for q in quadrants:
        q_u8 = q if q.dtype == np.uint8 else q.astype(np.uint8)
        gx = cv2.Sobel(q_u8, cv2.CV_64F, 1, 0, ksize=5)
        gy = cv2.Sobel(q_u8, cv2.CV_64F, 0, 1, ksize=5)
        mean_gx, mean_gy = float(gx.mean()), float(gy.mean())
        angle = np.arctan2(mean_gy, mean_gx)
        directions.append(angle)

    # Circular variance of estimated light directions across quadrants —
    # low variance = consistent lighting, high variance = possible composite.
    sin_sum = np.mean([np.sin(a) for a in directions])
    cos_sum = np.mean([np.cos(a) for a in directions])
    resultant_length = np.sqrt(sin_sum ** 2 + cos_sum ** 2)  # 1 = perfectly consistent, 0 = random
    lighting_consistency_score = float(np.clip(resultant_length, 0, 1))

    # Shadow consistency proxy: compare brightness histograms of quadrants —
    # large unexplained brightness deltas can indicate inconsistent lighting
    # or compositing (this is a coarse proxy, intentionally conservative).
    means = [float(q.mean()) for q in quadrants]
    brightness_std = float(np.std(means))
    shadow_consistency_score = float(np.clip(1.0 - (brightness_std / 60.0), 0, 1))

    if lighting_consistency_score < 0.4:
        notes.append("light_direction_varies_significantly_across_image_regions")
    if shadow_consistency_score < 0.4:
        notes.append("brightness_levels_inconsistent_across_image_regions")
    if not notes:
        notes.append("lighting_and_shadows_appear_consistent")

    return ReflectionConsistencyReport(
        lighting_consistency_score=round(lighting_consistency_score, 3),
        shadow_consistency_score=round(shadow_consistency_score, 3),
        notes=notes,
    )


def detect_ai_generated(image_path: str) -> AIGeneratedReport:
    signals = []
    img = cv2.imread(image_path)
    if img is None:
        return AIGeneratedReport(ai_generation_probability=0.0, manipulation_confidence=0.0, signals=["could_not_load_image"])

    gray_u8 = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = gray_u8.astype(np.float64)
    h, w = gray.shape

    # Signal 1: Noise floor analysis. Real camera sensor images carry a
    # characteristic high-frequency noise floor; many diffusion-model
    # outputs are unnaturally smooth in flat regions after upsampling.
    laplacian = cv2.Laplacian(gray_u8, cv2.CV_64F)
    noise_energy = float(np.var(laplacian))
    low_noise_signal = noise_energy < 15.0  # flat/smooth image, low high-freq energy
    if low_noise_signal:
        signals.append("unnaturally_low_high_frequency_noise")

    # Signal 2: FFT spectral analysis. Natural photos have a roughly
    # power-law falloff in frequency spectrum; some generative models leave
    # periodic grid-like artifacts (visible as symmetric peaks off the
    # origin in the magnitude spectrum) from upsampling/transposed-conv layers.
    f = np.fft.fft2(gray)
    fshift = np.fft.fftshift(f)
    magnitude = np.log(np.abs(fshift) + 1)
    center_y, center_x = h // 2, w // 2
    # mask out the DC/low-frequency center, look at energy concentration in
    # narrow symmetric bands vs. overall spread.
    # NOTE: cv2.circle requires a C-contiguous, OpenCV-compatible array
    # (uint8/float32) — np.zeros_like(magnitude) inherits float64 from the
    # FFT math above, which some OpenCV builds (notably arm64/macOS) reject
    # with a "Layout of the output array is incompatible" error even though
    # it works on other platforms. Always allocate the mask explicitly as
    # uint8 via np.zeros(..., dtype=np.uint8) rather than zeros_like here.
    ring_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(ring_mask, (center_x, center_y), max(min(h, w) // 6, 1), 1, thickness=4)
    ring_mask = ring_mask.astype(np.float64)
    ring_energy = float((magnitude * ring_mask).sum())
    total_energy = float(magnitude.sum()) + 1e-6
    ring_ratio = ring_energy / total_energy
    periodic_artifact_signal = ring_ratio > 0.012
    if periodic_artifact_signal:
        signals.append("periodic_frequency_artifacts_detected")

    # Signal 3: Color channel correlation. Diffusion outputs sometimes show
    # unusually high cross-channel correlation compared to natural sensor
    # photos (which have per-channel sensor noise / demosaicing artifacts).
    b, g, r = cv2.split(img.astype(np.float32))
    corr_rg = float(np.corrcoef(r.flatten(), g.flatten())[0, 1])
    corr_gb = float(np.corrcoef(g.flatten(), b.flatten())[0, 1])
    high_channel_corr = (corr_rg > 0.985) and (corr_gb > 0.985)
    if high_channel_corr:
        signals.append("unusually_high_cross_channel_color_correlation")

    global_score = 0.0
    if low_noise_signal:
        global_score += 0.35
    if periodic_artifact_signal:
        global_score += 0.35
    if high_channel_corr:
        global_score += 0.30

    # --- Localized/regional pass ---
    # Whole-image statistics are diluted when only a SMALL region of an
    # otherwise-real photo has been AI-edited/inpainted (e.g. a real laptop
    # photo with a crack inpainted onto the screen by an image model) — the
    # real camera noise/spectrum from the untouched 90%+ of the frame
    # dominates the average and hides the edit. To catch this, we tile the
    # image into a grid and look for any cell whose local noise statistics
    # deviate sharply from the OTHER cells in the SAME image, rather than
    # comparing against a fixed global threshold. This is a relative,
    # within-image comparison, which is what makes it sensitive to partial
    # edits that whole-image stats miss entirely.
    region_result = _detect_localized_anomaly(gray_u8)

    combined_score = float(np.clip(max(global_score, region_result["score"]), 0, 1))
    if region_result["anomalous_regions"]:
        signals.append(
            f"localized_noise_anomaly_in_{len(region_result['anomalous_regions'])}_region(s)_"
            f"inconsistent_with_rest_of_image"
        )

    if not signals:
        signals.append("no_strong_ai_generation_signals_detected")

    return AIGeneratedReport(
        ai_generation_probability=round(combined_score, 3),
        manipulation_confidence=round(combined_score * 0.85, 3),
        signals=signals,
    )


def _detect_localized_anomaly(gray_u8: np.ndarray, grid_size: int = 4) -> dict:
    """Splits the image into a grid_size x grid_size grid and computes
    per-cell noise energy (Laplacian variance) and local FFT high-frequency
    ratio. Returns a score based on how much the most anomalous cell
    deviates from the median of all cells in the SAME image — a real photo
    with one AI-inpainted region will show one or two cells with markedly
    different (usually lower) noise energy than the rest, even though the
    image's global average looks unremarkable.
    """
    h, w = gray_u8.shape
    cell_h, cell_w = h // grid_size, w // grid_size
    if cell_h < 16 or cell_w < 16:
        # Image too small to tile meaningfully — skip regional analysis
        # rather than producing noisy results on tiny crops.
        return {"score": 0.0, "anomalous_regions": []}

    cell_noise_energies = []
    cell_boxes = []
    for gy in range(grid_size):
        for gx in range(grid_size):
            y0, y1 = gy * cell_h, (gy + 1) * cell_h
            x0, x1 = gx * cell_w, (gx + 1) * cell_w
            cell = gray_u8[y0:y1, x0:x1]
            lap = cv2.Laplacian(cell, cv2.CV_64F)
            cell_noise_energies.append(float(np.var(lap)))
            cell_boxes.append((x0, y0, x1 - x0, y1 - y0))

    energies = np.array(cell_noise_energies)
    median_energy = float(np.median(energies))
    mad = float(np.median(np.abs(energies - median_energy))) + 1e-6  # median absolute deviation, robust to outliers

    anomalous_regions = []
    max_deviation_score = 0.0
    for i, energy in enumerate(energies):
        # A cell is anomalous if its noise energy is far BELOW the image's
        # own median (smoother than everything around it — consistent with
        # an inpainted/regenerated patch) by a robust z-score-like measure.
        deviation = (median_energy - energy) / mad
        if deviation > 3.0 and median_energy > 3.0:  # require the rest of the image to actually have texture to deviate from
            anomalous_regions.append(cell_boxes[i])
            max_deviation_score = max(max_deviation_score, min(deviation / 10.0, 1.0))

    # Only a fraction of cells being anomalous (not most/all) is the
    # meaningful signal — if MOST cells look "smooth", that's more likely a
    # genuinely low-texture photo (e.g. a plain wall) than a localized edit,
    # and is already partially captured by the global noise-floor signal.
    anomalous_fraction = len(anomalous_regions) / len(cell_boxes)
    if anomalous_fraction > 0.5:
        return {"score": 0.0, "anomalous_regions": []}

    return {"score": max_deviation_score, "anomalous_regions": anomalous_regions}
