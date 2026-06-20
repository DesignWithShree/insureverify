"""
Fraud Explanation Engine.

Every risk flag in the system is backed by specific, already-computed
numbers (an ELA score, an FFT ratio, a flagged grid region, a VLM's own
description, etc.) — this module's only job is to turn those numbers into a
structured, specific, plain-language explanation: WHAT was measured, WHAT
the measurement showed, and WHY that indicates possible tampering.

This is intentionally NOT a new detection mechanism — it adds zero new
judgment calls. It reads from PerImageAuthenticity (Stage 0's per-image
output, already fully computed by the time this runs) and produces a
FraudExplanation per image, which the API/UI can render inline (a one-line
summary) or expanded (the full evidence list).
"""
from __future__ import annotations
from typing import List
from pydantic import BaseModel, Field

from app.core.schemas import PerImageAuthenticity


class EvidenceItem(BaseModel):
    check: str            # human label for which test this came from
    measurement: str      # the actual number/observation
    interpretation: str   # why this measurement is suspicious (or not)
    severity: str         # "info" | "caution" | "high"


class FraudExplanation(BaseModel):
    image_path: str
    verdict: str  # "clean" | "suspicious" | "likely_manipulated"
    headline: str  # one-line inline summary
    evidence: List[EvidenceItem] = Field(default_factory=list)


def _severity_for_score(score: float, low: float, high: float) -> str:
    if score >= high:
        return "high"
    if score >= low:
        return "caution"
    return "info"


def explain_image_authenticity(pi: PerImageAuthenticity) -> FraudExplanation:
    evidence: List[EvidenceItem] = []

    # --- Metadata / EXIF ---
    if pi.metadata.suspicious_metadata:
        flag_descriptions = []
        for flag in pi.metadata.metadata_flags:
            if "no_exif_data_present" in flag:
                flag_descriptions.append(
                    "The image carries no EXIF metadata at all. Most phone/camera "
                    "photos retain capture details (camera model, timestamp); a "
                    "total absence is common for screenshots, re-saved images, or "
                    "files stripped during editing/download — not proof of tampering "
                    "on its own, but a softer corroborating signal."
                )
            elif "editing_software_detected" in flag:
                software = flag.split(":")[-1] if ":" in flag else "unknown software"
                flag_descriptions.append(
                    f"EXIF metadata explicitly records that this image was processed "
                    f"by editing software ('{software}'). This is a direct, factual "
                    f"trace left in the file by the editing tool itself, not an inference."
                )
            elif "ai_generation_software_detected" in flag:
                software = flag.split(":")[-1] if ":" in flag else "unknown tool"
                flag_descriptions.append(
                    f"EXIF metadata names an AI image-generation tool ('{software}') "
                    f"in the file's software tag — the strongest possible signal, "
                    f"since this is the editing tool identifying itself."
                )
            elif "resaved_after_capture_signature" in flag:
                flag_descriptions.append(
                    "The file has a 'last modified' timestamp distinct from its "
                    "original capture timestamp, combined with a recorded software "
                    "tag — together suggesting the file was reprocessed after the "
                    "original photo was taken."
                )
        if flag_descriptions:
            evidence.append(EvidenceItem(
                check="Metadata (EXIF) forensics",
                measurement="; ".join(pi.metadata.metadata_flags),
                interpretation=" ".join(flag_descriptions),
                severity="caution" if len(flag_descriptions) == 1 else "high",
            ))

    # --- ELA ---
    if pi.ela.manipulation_score > 0.1:
        n_regions = len(pi.ela.suspicious_regions)
        sev = _severity_for_score(pi.ela.manipulation_score, 0.15, 0.4)
        evidence.append(EvidenceItem(
            check="Error Level Analysis (ELA)",
            measurement=f"manipulation score {pi.ela.manipulation_score} "
                        f"({n_regions} flagged region{'s' if n_regions != 1 else ''} out of the image's grid)",
            interpretation=(
                "ELA re-compresses the image and measures how much each region's "
                "pixels change — regions edited or generated separately from the "
                "rest of the photo tend to show a different compression-error "
                "signature (either noticeably higher, consistent with a pasted-in "
                "patch, or noticeably lower, consistent with a smoothly AI-rendered "
                "edit) than the surrounding, untouched parts of the same image. "
                f"{n_regions} region(s) deviated enough to be flagged here."
            ),
            severity=sev,
        ))

    # --- AI-generation / localized anomaly signals ---
    ai = pi.ai_generated
    if ai.ai_generation_probability > 0.1:
        sev = _severity_for_score(ai.ai_generation_probability, 0.3, 0.55)
        signal_explanations = []
        for sig in ai.signals:
            if sig == "unnaturally_low_high_frequency_noise":
                signal_explanations.append(
                    "the image is unusually smooth at the pixel level — real camera "
                    "sensors leave a fine high-frequency noise texture even in flat "
                    "areas, which this image lacks across most of its frame"
                )
            elif sig == "periodic_frequency_artifacts_detected":
                signal_explanations.append(
                    "the image's frequency spectrum shows repeating, grid-like "
                    "patterns rather than the smooth falloff typical of a real photo "
                    "— a known fingerprint left by the upsampling layers inside many "
                    "generative image models"
                )
            elif sig == "unusually_high_cross_channel_color_correlation":
                signal_explanations.append(
                    "the red, green, and blue color channels are unusually tightly "
                    "correlated with each other — real camera sensors record each "
                    "channel slightly differently (sensor noise, demosaicing), so "
                    "near-perfect correlation across channels is atypical of a "
                    "genuine photo"
                )
            elif sig.startswith("localized_noise_anomaly_in"):
                signal_explanations.append(
                    "one or more specific regions of the image are noticeably "
                    "smoother than every other region in the SAME photo — this is "
                    "a within-image comparison, so it specifically catches a small "
                    "AI-edited patch on an otherwise genuine photo, which whole-image "
                    "statistics alone would miss"
                )
            elif sig.startswith("vlm_flagged_possible_digital_edit"):
                # Pull the model's own stated reason if present.
                reason = sig.split("_reason:")[-1] if "_reason:" in sig else None
                if reason:
                    signal_explanations.append(
                        f"a vision-language model inspected the image specifically "
                        f"for editing artifacts and reported: \"{reason}\""
                    )
                else:
                    signal_explanations.append(
                        "a vision-language model flagged the image as showing "
                        "possible signs of digital editing based on visual "
                        "inspection (lighting, edges, or texture inconsistencies)"
                    )
        if signal_explanations:
            evidence.append(EvidenceItem(
                check="AI-generation / digital-edit statistical analysis",
                measurement=f"probability {ai.ai_generation_probability} — " + "; ".join(ai.signals),
                interpretation="Specifically: " + "; and ".join(signal_explanations) + ".",
                severity=sev,
            ))

    # --- Reflection / lighting consistency ---
    refl = pi.reflection
    if refl.lighting_consistency_score < 0.5 or refl.shadow_consistency_score < 0.5:
        sev = "caution" if min(refl.lighting_consistency_score, refl.shadow_consistency_score) > 0.25 else "high"
        evidence.append(EvidenceItem(
            check="Lighting & shadow consistency",
            measurement=f"lighting consistency {refl.lighting_consistency_score}, "
                        f"shadow consistency {refl.shadow_consistency_score}",
            interpretation=(
                "The estimated light direction and brightness levels vary more "
                "than expected across different regions of the same image. A "
                "single real photo is lit by one consistent light source (or "
                "set of sources) throughout; a composite of two different images, "
                "or a region edited under different lighting, often shows this "
                "kind of mismatch between regions."
            ),
            severity=sev,
        ))

    # --- Determine overall verdict for this image ---
    high_count = sum(1 for e in evidence if e.severity == "high")
    caution_count = sum(1 for e in evidence if e.severity == "caution")

    if high_count >= 1 or pi.image_authenticity_score < 0.4:
        verdict = "likely_manipulated"
        headline = f"{high_count + caution_count} forensic signal(s) indicate this image may be edited or AI-generated."
    elif caution_count >= 1 or pi.image_authenticity_score < 0.65:
        verdict = "suspicious"
        headline = f"{caution_count} forensic signal(s) raised mild concern, but evidence is not conclusive."
    else:
        verdict = "clean"
        headline = "No significant forensic anomalies detected in this image."

    return FraudExplanation(
        image_path=pi.image_path,
        verdict=verdict,
        headline=headline,
        evidence=evidence,
    )
