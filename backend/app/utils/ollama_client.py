"""
Ollama client wrapper.

Uses local Ollama (free, offline) for:
- llava: vision-language analysis (Stage 5 — objective image description)
- llama3: text reasoning (claim understanding, story consistency, judge agent)

This mirrors the IntelliDoc stack (EasyOCR + pdfplumber/PyMuPDF for extraction,
Ollama llama3 + llava for reasoning), so the setup is the same: `ollama pull
llava` and `ollama pull llama3` before running the platform.
"""
from __future__ import annotations
import base64
import json
import os
import requests
from typing import Optional, Dict, Any

OLLAMA_HOST = "http://localhost:11434"
VISION_MODEL = "llava"
TEXT_MODEL = "llama3"
REQUEST_TIMEOUT = 45

# Set INSUREVERIFY_FAST_MODE=1 to skip ALL Ollama calls and run purely on
# the classical CV/OCR/regex fallbacks for every stage. This trades some
# narrative nuance for speed — useful for demos, testing, or low-spec
# machines where llava/llama3 inference is slow. Toggle back to 0 (or unset)
# to use the full LLM reasoning layer once you've confirmed Ollama performs
# acceptably on your hardware.
FAST_MODE = os.environ.get("INSUREVERIFY_FAST_MODE", "0") == "1"


def _image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def query_vision_model(image_path: str, prompt: str, json_mode: bool = False) -> str:
    """Sends an image + prompt to the local llava model via Ollama and
    returns the raw text response."""
    payload: Dict[str, Any] = {
        "model": VISION_MODEL,
        "prompt": prompt,
        "images": [_image_to_base64(image_path)],
        "stream": False,
    }
    if json_mode:
        payload["format"] = "json"
    try:
        resp = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("response", "")
    except Exception as e:
        return json.dumps({"error": f"ollama_vision_unavailable: {e}"})


def query_text_model(prompt: str, system: Optional[str] = None, json_mode: bool = False) -> str:
    """Sends a text prompt to the local llama3 model via Ollama and returns
    the raw text response."""
    payload: Dict[str, Any] = {
        "model": TEXT_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system
    if json_mode:
        payload["format"] = "json"
    try:
        resp = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("response", "")
    except Exception as e:
        return json.dumps({"error": f"ollama_text_unavailable: {e}"})


def is_ollama_available() -> bool:
    if FAST_MODE:
        return False
    try:
        resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False
