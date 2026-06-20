"""
Stage 0 — Evidence Authenticity Engine
Part B: Error Level Analysis (ELA).

ELA works by re-saving the image at a known JPEG quality and computing the
per-pixel difference from the original. Regions that were edited/pasted in
after the original capture tend to have different JPEG compression artifact
levels than the rest of the image, which shows up as brighter regions in the
ELA difference map. This is a real, well-established forensic technique
(not a stub) — it just isn't a silver bullet, hence we combine it with other
signals in the aggregate authenticity score.

Two passes are run at different JPEG quality levels (90 and 70) and the
results are combined — a region that stands out consistently across both
quality levels is a much stronger signal than one that only appears at a
single, somewhat arbitrary quality setting.

Detection also checks for regions that are ABNORMALLY LOW in error, not
just abnormally high. A naive splice (cut-and-paste from another JPEG) tends
to show up as a region with MORE error than its surroundings (mismatched
prior compression history). But a smoothly blended/inpainted edit — the kind
modern AI image editors (Gemini, GPT-4o image tools, etc.) specifically aim
to produce — can instead show up as a region with LESS error than its
surroundings, because the edited pixels were freshly rendered with no
underlying JPEG block-grid history to clash with. Catching only the "too
high" direction misses exactly this increasingly common edit style.
"""
from __future__ import annotations
import io
import numpy as np
from PIL import Image, ImageChops

from app.core.schemas import ELAReport


def _single_quality_ela_map(original: Image.Image, quality: int, scale: int) -> np.ndarray:
    buffer = io.BytesIO()
    original.save(buffer, "JPEG", quality=quality)
    buffer.seek(0)
    resaved = Image.open(buffer)
    diff = ImageChops.difference(original, resaved)
    diff_arr = np.array(diff).astype(np.float32)
    max_diff = diff_arr.max() if diff_arr.max() > 0 else 1.0
    scale_factor = min(255.0 / max_diff, scale)
    amplified = np.clip(diff_arr * scale_factor, 0, 255)
    return amplified.mean(axis=2)


def compute_ela(image_path: str, quality: int = 90, scale: int = 15) -> ELAReport:
    try:
        original = Image.open(image_path).convert("RGB")
    except Exception:
        return ELAReport(ela_mean=0.0, ela_max=0.0, suspicious_regions=[], manipulation_score=0.0)

    gray_q90 = _single_quality_ela_map(original, 90, scale)
    gray_q70 = _single_quality_ela_map(original, 70, scale)
    gray = (gray_q90 + gray_q70) / 2.0  # combined map for reported mean/max stats

    ela_mean = float(gray.mean())
    ela_max = float(gray.max())

    h, w = gray.shape
    block = 32
    suspicious_regions = []
    high_thresh = ela_mean + 2.0 * float(gray.std())
    # Percentile-based low threshold instead of mean-minus-std: with the
    # high variance typical of real ELA maps, "mean - 2*std" frequently goes
    # negative and clamps to 0, making the low-side check unreachable for
    # any real photo. The 10th percentile of the image's OWN block means is
    # a relative, self-calibrating threshold that stays meaningful regardless
    # of the image's overall noise level.
    block_means_q90 = []
    for y in range(0, h - block, block):
        for x in range(0, w - block, block):
            block_means_q90.append(gray_q90[y:y + block, x:x + block].mean())
    low_thresh = float(np.percentile(block_means_q90, 10)) * 0.5 if block_means_q90 else 0.0

    for y in range(0, h - block, block):
        for x in range(0, w - block, block):
            patch_q90 = gray_q90[y:y + block, x:x + block]
            patch_q70 = gray_q70[y:y + block, x:x + block]
            mean_q90, mean_q70 = patch_q90.mean(), patch_q70.mean()

            # "Too high" direction (classic splice signal) — require it to
            # show up at BOTH quality levels, not just one, to cut down on
            # single-quality noise/false positives.
            too_high = mean_q90 > high_thresh and mean_q70 > high_thresh
            # "Too low" direction (smooth-inpaint signal) — same
            # both-qualities requirement, and only meaningful if the rest of
            # the image actually has measurable texture to be low relative to.
            too_low = mean_q90 < low_thresh and mean_q70 < low_thresh and ela_mean > 1.0

            if too_high or too_low:
                suspicious_regions.append([int(x), int(y), block, block])

    area_fraction = len(suspicious_regions) * (block * block) / (h * w) if h * w else 0.0
    region_signal = min(area_fraction * 4, 1.0) if suspicious_regions else 0.0
    deviation_ratio = min((ela_max / (ela_mean + 1e-6)) / 80.0, 1.0)
    if suspicious_regions:
        manipulation_score = float(np.clip(0.7 * region_signal + 0.3 * deviation_ratio, 0, 1))
    else:
        manipulation_score = float(np.clip(0.1 * deviation_ratio, 0, 0.15))

    return ELAReport(
        ela_mean=round(ela_mean, 3),
        ela_max=round(ela_max, 3),
        suspicious_regions=suspicious_regions[:25],
        manipulation_score=round(manipulation_score, 3),
    )
