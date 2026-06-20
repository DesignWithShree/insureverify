"""
Stage 2 — Possession Verification Engine.

Generates a unique, single-use challenge code per claim (e.g. CLAIM-58291).
The claimant must write this code on paper, place it next to the object, and
photograph/film it together with the damage. This defeats the most common
low-effort fraud pattern: submitting a stock photo or an old/borrowed photo,
since the attacker would need to know the code in advance (issued only after
claim creation) and produce a fresh photo containing it.
"""
from __future__ import annotations
import random
import string
from typing import List

from app.core.schemas import PossessionEngineOutput, RiskFlag
from app.utils.ocr import extract_text


def generate_challenge_code(claim_id: str) -> str:
    suffix = "".join(random.choices(string.digits, k=5))
    return f"CLAIM-{suffix}"


def _normalize(text: str) -> str:
    return "".join(text.upper().split())


def run_possession_engine(image_paths: List[str], challenge_code: str) -> PossessionEngineOutput:
    detected_codes: List[str] = []
    target = _normalize(challenge_code)

    for path in image_paths:
        texts = extract_text(path)
        joined = _normalize(" ".join(texts))
        # Look for the code as a contiguous substring, tolerant of OCR
        # inserting/dropping whitespace around the hyphen.
        candidates = [_normalize(t) for t in texts]
        for c in candidates:
            if target in c or c in target:
                detected_codes.append(c)
        if target in joined and target not in detected_codes:
            detected_codes.append(target)

    detected = len(detected_codes) > 0
    possession_score = 0.95 if detected else 0.1
    flags = [] if detected else [RiskFlag.possession_not_verified]

    return PossessionEngineOutput(
        challenge_code=challenge_code,
        challenge_code_detected=detected,
        detected_codes=list(dict.fromkeys(detected_codes)),
        possession_score=possession_score,
        flags=flags,
    )
