"""
OCR utility — wraps EasyOCR (matches the IntelliDoc stack: EasyOCR for text
extraction). The reader is lazily instantiated and cached at module level
because loading the EasyOCR model is expensive (~seconds) and we don't want
to repeat that cost per image.
"""
from __future__ import annotations
from typing import List, Tuple
import threading

_reader = None
_lock = threading.Lock()


def get_reader():
    global _reader
    if _reader is None:
        with _lock:
            if _reader is None:
                import easyocr
                # English only by default; extend lang list if you need
                # multi-language plate/label recognition.
                _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def extract_text(image_path: str) -> List[str]:
    """Returns a flat list of detected text strings, highest-confidence first."""
    try:
        reader = get_reader()
        results = reader.readtext(image_path)  # [(bbox, text, confidence), ...]
        results.sort(key=lambda r: r[2], reverse=True)
        return [text.strip() for _, text, conf in results if conf > 0.25 and text.strip()]
    except Exception as e:
        # OCR is a best-effort signal — if the model/runtime isn't available
        # (e.g. EasyOCR not installed yet), degrade gracefully rather than
        # crashing the whole pipeline.
        return []
