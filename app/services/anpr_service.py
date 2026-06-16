"""
anpr_service.py — Automatic Number-Plate Recognition.

Pipeline:
  1. Decode image (OpenCV).
  2. Detect plate-like quadrilateral regions (grayscale → bilateral filter →
     Canny edges → contour approximation, filtered by aspect ratio).
  3. OCR each candidate (Tesseract, single-line PSM, alphanumeric whitelist).
  4. Normalize + validate against Indian plate formats; return the best match.

OCR backend is pluggable and optional: if Tesseract isn't installed the pipeline
degrades gracefully (`ocr_available: False`) instead of crashing. The Tesseract
binary is auto-located across common install paths (Windows) and the PATH
(Linux/Docker). Plate validation/normalization is pure and fully unit-tested.
"""
import os
import re

# Standard Indian plate, e.g. KA01AB1234 / KA1A1234 ; plus BH series 21BH1234AA.
_PLATE_RE = re.compile(r"^[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{4}$")
_BH_RE = re.compile(r"^\d{2}BH\d{4}[A-Z]{1,2}$")

_TESSERACT_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
]


def normalize_plate(text: str) -> str:
    """Uppercase and strip everything that isn't A–Z/0–9."""
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


def is_valid_plate(text: str) -> bool:
    t = normalize_plate(text)
    return bool(_PLATE_RE.match(t) or _BH_RE.match(t))


def _configure_tesseract():
    """Point pytesseract at the binary; return True if OCR is usable."""
    try:
        import pytesseract
    except Exception:
        return None
    try:
        pytesseract.get_tesseract_version()
        return pytesseract
    except Exception:
        for path in _TESSERACT_CANDIDATES:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                try:
                    pytesseract.get_tesseract_version()
                    return pytesseract
                except Exception:
                    continue
    return None


def ocr_available() -> bool:
    return _configure_tesseract() is not None


def _detect_candidates(gray):
    """Return cropped grayscale regions likely to contain a plate (widest first)."""
    import cv2

    filtered = cv2.bilateralFilter(gray, 11, 17, 17)
    edges = cv2.Canny(filtered, 30, 200)
    contours, _ = cv2.findContours(edges.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:12]
    crops = []
    h_img, w_img = gray.shape[:2]
    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.018 * peri, True)
        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(approx)
            if h == 0:
                continue
            ar = w / float(h)
            if 2.0 <= ar <= 6.0 and w > w_img * 0.15:
                crops.append(gray[y:y + h, x:x + w])
    return crops


def recognize_plate(image_bytes: bytes) -> dict:
    """Detect + OCR a number plate from raw image bytes."""
    result = {"plate": None, "valid": False, "confidence": 0.0,
              "candidates": [], "ocr_available": False}
    try:
        import cv2
        import numpy as np
    except Exception:
        result["error"] = "opencv not available"
        return result

    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        result["error"] = "could not decode image"
        return result
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    pytesseract = _configure_tesseract()
    result["ocr_available"] = pytesseract is not None
    # OCR the detected regions, then the whole frame as a fallback.
    regions = _detect_candidates(gray) + [gray]
    if not result["ocr_available"]:
        return result

    cfg = "--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    best = None
    for region in regions:
        if region is None or region.size == 0:
            continue
        text = normalize_plate(pytesseract.image_to_string(region, config=cfg))
        if not text:
            continue
        result["candidates"].append(text)
        if is_valid_plate(text) and (best is None or len(text) > len(best)):
            best = text

    if best:
        result.update(plate=best, valid=True, confidence=0.9)
    elif result["candidates"]:
        # Return the longest raw guess even if it doesn't fully validate.
        guess = max(result["candidates"], key=len)
        result.update(plate=guess, valid=is_valid_plate(guess), confidence=0.5)
    return result
