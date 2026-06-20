"""
Stage 0 — Evidence Authenticity Engine
Part C: Perceptual hashing (pHash) for duplicate / reused evidence detection.

This is also reused by the bonus Fraud Network Engine to detect the SAME
photo being submitted across different claims (a strong fraud signal: e.g.
the same stock photo of a cracked screen used by two different "unrelated"
users, or the same user resubmitting old damage for a new claim).
"""
from __future__ import annotations
import imagehash
from PIL import Image


def compute_phash(image_path: str) -> str:
    try:
        img = Image.open(image_path)
        return str(imagehash.phash(img))
    except Exception:
        return ""


def hamming_distance(hash1: str, hash2: str) -> int:
    try:
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        return h1 - h2
    except Exception:
        return 999


def is_likely_duplicate(hash1: str, hash2: str, threshold: int = 8) -> bool:
    """pHash hamming distance <= threshold (out of 64 bits) is a strong
    near-duplicate signal — this threshold is a commonly used default for
    'visually identical or near-identical' images, tolerant of recompression,
    minor crop, or resize, but not tolerant of genuinely different photos."""
    if not hash1 or not hash2:
        return False
    return hamming_distance(hash1, hash2) <= threshold
