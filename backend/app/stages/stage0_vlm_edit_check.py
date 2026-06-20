"""
Stage 0 — Evidence Authenticity Engine
Part F: VLM-based semantic editing check.

The pixel-statistics checks in stage0_visual_forensics.py and stage0_ela.py
are blind to anything that doesn't show up as a measurable statistical
anomaly — which, deliberately, is what modern AI image editors (Gemini,
GPT-4o's image tool, etc.) are optimized to avoid leaving behind. A
semantic/visual judgment from a vision-language model is a genuinely
different kind of signal: it can notice things like inconsistent shadow
direction around an edited region, a crack that doesn't follow the
material's real fracture mechanics, unnatural edge blending, or lighting
that doesn't match between a part of the image and its surroundings — the
same kinds of cues a trained human investigator would look for, rather than
a pixel-level statistical test.

This is intentionally a SEPARATE, independent check from Stage 5 (Vision-
Language Analysis) — Stage 5 describes what damage is visible, this asks a
narrower, specifically adversarial question: "does anything about this
image look digitally edited or inpainted, independent of the damage type."
Asking both means the VLM never has to do two different jobs in one prompt,
which keeps each answer more reliable.

Like every other Ollama-dependent stage, this fails gracefully (returns a
neutral/uninformative result) if Ollama isn't running, rather than blocking
the pipeline or raising an exception.
"""
from __future__ import annotations
import json
import re
from typing import Optional

from app.utils.ollama_client import query_vision_model, is_ollama_available

EDIT_DETECTION_PROMPT = """You are a forensic image examiner. Look closely at this photo,
which was submitted as insurance evidence. Your ONLY job right now is to judge whether the
image shows signs of digital editing or AI-based image generation/inpainting — NOT to describe
what damage is shown.

Look specifically for:
- Inconsistent lighting or shadow direction between different parts of the image
- Edges around a feature (like a crack, dent, or mark) that look unnaturally smooth, blended, or "painted on" rather than physically part of the material
- A damage feature whose texture, sharpness, or grain doesn't match the surrounding surface
- Reflections, textures, or fine detail that look subtly unrealistic, melted, or inconsistent
- Any region that looks like it was pasted in or generated separately from the rest of the photo

Respond ONLY in this exact JSON structure, no other text:
{
  "looks_edited": <true|false>,
  "confidence": <float 0 to 1, your confidence in the looks_edited judgment>,
  "suspicious_region_description": "<brief description of WHERE and WHY, or empty string if looks_edited is false>"
}"""


def _parse_response(raw: str) -> Optional[dict]:
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


def check_for_semantic_edit_artifacts(image_path: str) -> dict:
    """Returns a dict with keys: looks_edited (bool), confidence (float),
    description (str), available (bool — False means Ollama wasn't running
    and this check did not actually run)."""
    if not is_ollama_available():
        return {"looks_edited": False, "confidence": 0.0, "description": "", "available": False}

    raw = query_vision_model(image_path, EDIT_DETECTION_PROMPT, json_mode=True)
    parsed = _parse_response(raw)

    if not parsed:
        return {"looks_edited": False, "confidence": 0.0, "description": "", "available": False}

    return {
        "looks_edited": bool(parsed.get("looks_edited", False)),
        "confidence": float(parsed.get("confidence", 0.0)),
        "description": str(parsed.get("suspicious_region_description", "")),
        "available": True,
    }
