"""ANPR: plate validation/normalization (pure) + detection/OCR pipeline + API."""
import io

import pytest

from app.services import anpr_service


# ---------------- pure validation (deterministic) ----------------
@pytest.mark.parametrize("raw,expected", [
    ("KA01AB1234", "KA01AB1234"),
    ("ka 01 ab 1234", "KA01AB1234"),
    ("KA-01-AB-1234", "KA01AB1234"),
])
def test_normalize_plate(raw, expected):
    assert anpr_service.normalize_plate(raw) == expected


@pytest.mark.parametrize("plate", ["KA01AB1234", "MH12DE1433", "KA1A1234", "21BH1234AA"])
def test_valid_plates(plate):
    assert anpr_service.is_valid_plate(plate)


@pytest.mark.parametrize("plate", ["", "HELLO", "1234", "KA01AB123", "ZZ99ZZ99999"])
def test_invalid_plates(plate):
    assert not anpr_service.is_valid_plate(plate)


# ---------------- pipeline ----------------
def _plate_image(text="KA01AB1234"):
    """Render a clean high-contrast plate image for OCR."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (640, 200), "white")
    d = ImageDraw.Draw(img)
    font = None
    for path in [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        try:
            font = ImageFont.truetype(path, 110)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    d.rectangle([10, 10, 630, 190], outline="black", width=6)
    d.text((40, 40), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_recognize_returns_structure():
    result = anpr_service.recognize_plate(_plate_image())
    for key in ("plate", "valid", "confidence", "candidates", "ocr_available"):
        assert key in result


def test_recognize_handles_garbage_bytes():
    result = anpr_service.recognize_plate(b"not-an-image")
    assert result["plate"] is None  # graceful, no crash


@pytest.mark.skipif(not anpr_service.ocr_available(), reason="Tesseract not installed")
def test_recognize_reads_clear_plate():
    result = anpr_service.recognize_plate(_plate_image("KA01AB1234"))
    assert result["ocr_available"] is True
    assert result["candidates"], "OCR should emit at least one candidate for a clear plate"


# ---------------- API ----------------
def test_anpr_api_requires_image(client):
    assert client.post("/api/v1/anpr").status_code == 400


def test_anpr_api_processes_image(client):
    data = {"image": (io.BytesIO(_plate_image()), "plate.png")}
    r = client.post("/api/v1/anpr", data=data, content_type="multipart/form-data")
    # 200 when OCR engine present, 503 when not — both are valid, structured responses.
    assert r.status_code in (200, 503)
    assert "ocr_available" in r.get_json()
