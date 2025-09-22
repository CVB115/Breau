# app/routers/ocr_frontend.py
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Any, Dict
import io

router = APIRouter(prefix="/ocr", tags=["ocr"])

# Optional OCR backends
try:
    import easyocr  # type: ignore
except Exception:
    easyocr = None  # type: ignore

try:
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore
except Exception:
    pytesseract = None  # type: ignore
    Image = None  # type: ignore

# Our post-processor
try:
    from breau_backend.app.services.router_helpers.ocr_helpers import extract_fields_from_text
except Exception:
    from app.services.router_helpers.ocr_helpers import extract_fields_from_text  # type: ignore

def _easyocr_text(img_bytes: bytes) -> str:
    reader = easyocr.Reader(["en"], gpu=False)
    arr = io.BytesIO(img_bytes)
    # EasyOCR wants a path/ndarray; simplest path is open with PIL if present
    try:
        from PIL import Image
        import numpy as np
        im = Image.open(arr).convert("RGB")
        nd = np.array(im)
        result = reader.readtext(nd, detail=0, paragraph=True)
        return "\n".join(result)
    except Exception:
        # fallback to bytes pathless read
        result = reader.readtext(arr.getvalue(), detail=0, paragraph=True)
        if isinstance(result, list):
            return "\n".join(result)
        return str(result)

def _tesseract_text(img_bytes: bytes) -> str:
    if Image is None or pytesseract is None:
        raise RuntimeError("pytesseract not available")
    im = Image.open(io.BytesIO(img_bytes))
    return pytesseract.image_to_string(im)

@router.post("/extract")
async def extract(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Returns:
      {
        ok: boolean,
        text: string,            # raw OCR
        fields: { ... },         # structured map (origin, process, variety[], flavor_notes[], name?, roaster?)
        error: string?           # if any
      }
    """
    try:
        data = await file.read()
        raw_text = ""
        if easyocr is not None:
            try:
                raw_text = _easyocr_text(data)
            except Exception as e:
                raw_text = ""
        if not raw_text and pytesseract is not None:
            try:
                raw_text = _tesseract_text(data)
            except Exception:
                pass
        if not raw_text:
            return {"ok": False, "text": "", "fields": {}, "error": "server_ocr_unavailable"}

        fields = extract_fields_from_text(raw_text)
        return {"ok": True, "text": raw_text, "fields": fields}
    except Exception as e:
        return {"ok": False, "text": "", "fields": {}, "error": f"{type(e).__name__}: {e}"}
