# breau_backend/app/routers/ocr.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from typing import Dict, Any, List, Optional
import os
import platform
import re
import io

# ---- OCR deps ----
# pip install pillow pytesseract
from PIL import Image
import pytesseract

router = APIRouter()
_WARMED = False

# --- Make pytesseract work reliably on Windows ---
# 1) If you set BREAU_TESSERACT_CMD, we prefer that.
# 2) Else, if on Windows and the common path exists, we set it.
# 3) Else, we rely on PATH (works on Linux/macOS with apt/brew).
TESS_CMD_ENV = os.getenv("BREAU_TESSERACT_CMD")
if TESS_CMD_ENV and os.path.exists(TESS_CMD_ENV):
    pytesseract.pytesseract.tesseract_cmd = TESS_CMD_ENV
elif platform.system().lower().startswith("win"):
    default_win_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(default_win_path):
        pytesseract.pytesseract.tesseract_cmd = default_win_path
# (If neither path exists, calling image_to_string will raise a clear error which we surface.)

async def _warmup_impl():
    global _WARMED
    if _WARMED:
        return {"ok": True, "warmed": True}
    # For pytesseract there isn't much to preload, but we keep a warmup endpoint for symmetry.
    _WARMED = True
    return {"ok": True, "warmed": True}

@router.get("/ocr/warmup")
async def ocr_warmup():
    try:
        return await _warmup_impl()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" •|")

def _title(s: str) -> str:
    return " ".join(w[:1].upper() + w[1:] if w else w for w in re.split(r"[ -]", s))

def _parse_fields(text: str) -> Dict[str, Any]:
    t = text.replace("\r", " ")
    tl = t.lower()

    def label_rx(name: str) -> re.Pattern:
        return re.compile(rf"\b(?:{name})\s*[:\-]\s*([^\n]+)", re.IGNORECASE)

    fields: Dict[str, Any] = {
        "origin": None,
        "process": None,
        "variety": None,        # CSV for UI
        "roast_level": None,
        "flavor_notes": [],     # list[str]
    }

    # Origin
    m = label_rx(r"origin|region|farm|country").search(t)
    if m:
        fields["origin"] = _clean(m.group(1))
    else:
        countries = [
            "ethiopia","kenya","colombia","brazil","guatemala","el salvador",
            "costa rica","uganda","rwanda","peru","yemen","panama","indonesia"
        ]
        for c in countries:
            if c in tl:
                fields["origin"] = _title(c)
                break

    # Process
    m = label_rx(r"process|proc\.?").search(t)
    if m:
        fields["process"] = _clean(m.group(1))
    else:
        procs = [
            "washed","natural","anaerobic","honey","carbonic maceration",
            "double","semi-washed","wet-hulled"
        ]
        for p in procs:
            if p in tl:
                fields["process"] = _title(p)
                break

    # Variety
    m = label_rx(r"variety|varietal").search(t)
    if m:
        fields["variety"] = _clean(m.group(1))
    else:
        varietals = [
            "bourbon","typica","caturra","catuai","gesha","geisha","sl28","sl34",
            "heirloom","pacamara","pacas","maragogipe","castillo","villalobos",
            "villa sarchi","pink bourbon","java","sidra","mundo novo","catimor",
            "ruiru 11","batian"
        ]
        hits: List[str] = []
        for v in varietals:
            if v in tl:
                hits.append(_title(v))
        if hits:
            fields["variety"] = ", ".join(sorted(set(hits)))

    # Roast level
    m = label_rx(r"roast(?:\s*level)?").search(t)
    if m:
        fields["roast_level"] = _clean(m.group(1))
    else:
        roasts = ["light","light-medium","medium","medium-dark","dark"]
        for r in roasts:
            if r in tl:
                fields["roast_level"] = _title(r)
                break

    # Tasting notes
    m = label_rx(r"(?:tasting\s*)?notes|flavour|flavor").search(t)
    if m:
        chunk = _clean(m.group(1))
        parts = [p.strip() for p in re.split(r"[•,;·/]", chunk) if p.strip()]
        if parts:
            fields["flavor_notes"] = parts

    return fields

@router.post("/ocr/extract")
async def ocr_extract(file: UploadFile = File(...)):
    """Accepts an image and returns OCR text + parsed fields.

    Response shape matches the frontend expectation:
    { "raw_text": str, "parsed": { ... } }
    """
    await _warmup_impl()
    try:
        raw = await file.read()
        if not raw:
            raise ValueError("Empty file")

        image = Image.open(io.BytesIO(raw)).convert("RGB")

        # Basic Tesseract OCR (add more langs if needed, e.g., 'eng+ind')
        text: str = pytesseract.image_to_string(image, lang="eng")

        fields = _parse_fields(text)

        return {
            "raw_text": text,
            "parsed": fields,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ocr/parse")
async def ocr_parse(payload: Dict[str, str] = Body(...)):
    """Re-parse edited raw text (used by 'Apply again' on the Beans page)."""
    try:
        raw_text = payload.get("raw_text", "")
        if not isinstance(raw_text, str) or not raw_text.strip():
            raise ValueError("raw_text is required")
        fields = _parse_fields(raw_text)
        return {"parsed": fields}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
