from __future__ import annotations
from typing import List, Dict, Any, Optional
from pathlib import Path
import os, re, unicodedata, io

# --- Optional OCR backends (unchanged) ---
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

# --- DATA DIR (portable) ---
DATA_DIR = Path(os.getenv("DATA_DIR", "./data")).resolve()
def ensure_dir(p: Path) -> None: p.mkdir(parents=True, exist_ok=True)
def safe_filename(name: str) -> str:
    s = unicodedata.normalize("NFKC", name or "")
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")
    return s or "upload"

# ------------------- Public helpers used elsewhere (unchanged) -------------------
def _langs() -> List[str]:
    raw = os.getenv("OCR_LANGS", "en")
    return [s.strip() for s in raw.split(",") if s.strip()]

def save_upload_temp(filename: str, content: bytes) -> Path:
    tmp_dir = DATA_DIR / "tmp"; ensure_dir(tmp_dir)
    path = tmp_dir / safe_filename(filename)
    with open(path, "wb") as f: f.write(content)
    return path

def extract_label_fields(image_path: Path) -> Dict[str, Any]:
    """Back-compat: OCR an image file and return structured fields ({ok,text,fields,error?})."""
    text = ""
    if easyocr is not None:
        try:
            reader = easyocr.Reader(_langs(), gpu=False)
            lines = reader.readtext(str(image_path), detail=0, paragraph=True)
            text = "\n".join(lines) if isinstance(lines, list) else str(lines)
        except Exception:
            text = ""
    if not text and pytesseract is not None and Image is not None:
        try:
            text = pytesseract.image_to_string(Image.open(image_path))
        except Exception:
            text = ""
    if not text:
        return {"ok": False, "text": "", "fields": {}, "error": "server_ocr_unavailable"}
    return {"ok": True, "text": text, "fields": extract_fields_from_text(text)}

# ---------------------- Text parsing & normalization ---------------------------

# Config toggles
ENABLE_NAME_GUESS = False   # <-- per your request, do NOT auto-fill name
ENABLE_ROASTER_GUESS = False  # <-- do NOT auto-fill roaster

COUNTRIES = {
    "ethiopia","kenya","colombia","brazil","guatemala","honduras","el salvador","costa rica",
    "nicaragua","panama","yemen","rwanda","burundi","uganda","tanzania","peru","bolivia",
    "mexico","india","indonesia","papua new guinea","china","laos","myanmar","vietnam"
}

# Canonical process families + rich aliases
PROCESS_CANON = {
    "washed": {
        "aliases": ["washed", "double washed", "triple washed", "fully washed", "wet process", "wet-processed", "washed process"],
        "tags":    ["washed"]
    },
    "natural": {
        "aliases": ["natural", "dry process", "sun-dried", "natural process"],
        "tags":    ["natural"]
    },
    "honey": {
        "aliases": ["honey", "pulped natural", "semi-washed", "semi washed"],
        "tags":    ["honey"]
    },
    "anaerobic": {
        "aliases": ["anaerobic", "carbonic maceration", "carbonic", "co2", "limited oxygen", "sealed tank"],
        "tags":    ["anaerobic"]
    },
    "wet-hulled": {
        "aliases": ["wet-hulled", "giling basah", "giling-basah"],
        "tags":    ["wet-hulled"]
    },
    # Modifiers (color honeys, fermentation styles, etc) we’ll attach as tags:
}
PROCESS_MODIFIERS = {
    # color honeys
    "black honey": ["black honey"],
    "red honey":   ["red honey"],
    "yellow honey":["yellow honey"],
    "white honey": ["white honey"],
    # fermentation styles
    "lactic":      ["lactic", "lactic fermentation"],
    "yeast":       ["yeast", "yeast inoculated", "yeast fermentation"],
    "thermal shock":["thermal shock"],
    "extended":    ["extended fermentation", "long fermentation"],
    "double":      ["double washed", "double anaerobic", "double", "twice washed"],
    "experimental":["experimental"],
}

VARIETY_KEYS = ["variety", "varieties", "varietal", "blend"]

FLAVOR_MULTIWORD = {
    "black grapes", "rum & raisin", "rum and raisin", "dried pineapple", "green apple",
    "red apple", "yellow plum", "stone fruit", "brown sugar", "milk chocolate",
    "dried apricot", "black tea"
}
FLAVOR_SINGLE = {
    "blackberry","blueberry","strawberry","raspberry","grape","grapes","orange","lemon",
    "lime","grapefruit","apricot","peach","plum","pineapple","mango","papaya",
    "cherry","cocoa","chocolate","caramel","toffee","molasses","honey","floral",
    "jasmine","bergamot","spice","clove","cinnamon","nutmeg","almond","hazelnut",
    "rum","raisin","vanilla","brown sugar","sugarcane","currant","hibiscus"
}

def _norm(s: str) -> str:
    return unicodedata.normalize("NFKC", (s or "")).replace("—", "-").strip()

def _clean_line(s: str) -> str:
    s = _norm(s)
    s = re.sub(r"[|=_••·•]+", " ", s)  # strip OCR bars/dots
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s

def _is_shouty(s: str) -> bool:
    letters = re.findall(r"[A-Za-z]", s)
    return bool(letters) and (sum(1 for c in letters if c.isupper()) / max(1, len(letters)) >= 0.7)

def split_lines(text: str) -> List[str]:
    raw = text.replace("\r", "\n").split("\n")
    return [_clean_line(x) for x in raw if _clean_line(x)]

# ---------- Origin(s) ----------
def detect_origins(lines: List[str]) -> List[str]:
    found = []
    flat = " ".join(lines).lower()
    # explicit "origin:" or country tokens anywhere
    for c in COUNTRIES:
        if re.search(rf"\b{re.escape(c)}\b", flat):
            found.append(c.title())
    # de-dup preserve order
    out, seen = [], set()
    for x in found:
        if x.lower() in seen: continue
        seen.add(x.lower()); out.append(x)
    return out

# ---------- Process (canonical + tags) ----------
def detect_process(lines: List[str]) -> Dict[str, Any]:
    flat = " ".join(lines).lower()
    canon = None
    for key, cfg in PROCESS_CANON.items():
        for alias in cfg["aliases"]:
            if re.search(rf"\b{re.escape(alias)}\b", flat):
                canon = key
                break
        if canon: break

    tags = set()
    # attach modifiers present in text
    for tag, kws in PROCESS_MODIFIERS.items():
        for kw in kws:
            if re.search(rf"\b{re.escape(kw)}\b", flat):
                tags.add(tag)
                break

    # Disambiguate honey flavors vs honey process: if "honey" appears next to
    # "process" or "method" or in a "Variety/Process" section, treat as process;
    # else if only in flavor block and no process context, don't force "honey".
    if "honey" in flat and not canon:
        if re.search(r"(?i)(process|method).*honey|honey.*(process|method)", flat):
            canon = "honey"

    # If we saw "double washed" etc, ensure base is set accordingly
    if not canon and any(w in flat for w in ["washed", "wet process", "fully washed"]):
        canon = "washed"
    if not canon and any(w in flat for w in ["natural", "dry process"]):
        canon = "natural"

    return {
        "process": canon,                # canonical family or None
        "process_tags": sorted(tags),    # modifiers like ["double","lactic","black honey"]
    }

# ---------- Varieties (handles blends) ----------
def detect_varieties_and_blend(lines: List[str]) -> Dict[str, Any]:
    varieties: List[str] = []
    is_blend = False
    for ln in lines:
        low = ln.lower()
        if any(low.startswith(k) for k in VARIETY_KEYS) or re.search(r"(?i)\bblend\b", low):
            is_blend = True if "blend" in low else is_blend
            rest = re.sub(r"(?i)^(varieties?|varietal|blend)\s*[:\-]?", "", ln).strip()
            # normalize common OCR quirks
            rest = rest.replace("sl ", "sl").replace("sl,", "sl ")
            parts = re.split(r"[,/;•]| and ", rest)
            for p in parts:
                p = _clean_line(p)
                if not p: continue
                p = re.sub(r"\bsl\s* ?(\d+)\b", lambda m: f"SL {m.group(1)}", p, flags=re.I)
                p = re.sub(r"ruiru\s*11", "Ruiru 11", p, flags=re.I)
                p = re.sub(r"batian", "Batian", p, flags=re.I)
                varieties.append(p.title())
    # de-dup preserve order
    out, seen = [], set()
    for v in varieties:
        k = v.lower()
        if k in seen: continue
        seen.add(k); out.append(v)
    return {"variety": out, "is_blend": bool(is_blend or len(out) > 1)}

# ---------- Flavor notes (same approach, robust) ----------
FLAVOR_HEADER_RX = re.compile(r"(?i)\b(producer|process|variet|roast\s*date|roaster|espresso\s*roast)\b")
def _as_tokens(lines: List[str]) -> List[str]:
    toks = []
    for ln in lines:
        s = _norm(ln).lower().replace("&", " and ")
        s = re.sub(r"[^a-z0-9\s\-]", " ", s)
        s = re.sub(r"\s{2,}", " ", s).strip()
        if s: toks.append(s)
    return toks

def detect_flavor_notes(lines: List[str]) -> List[str]:
    shouty = [ln for ln in lines if _is_shouty(ln)]
    shouty = [ln for ln in shouty if not FLAVOR_HEADER_RX.search(ln)]
    if len(shouty) >= 2:
        block = []
        for ln in shouty:
            t = re.sub(r"[^A-Za-z& \-]", " ", ln).strip()
            if t: block.append(t)
        cand = " ".join(block).lower().replace("&", " and ")
        notes = set()
        for mw in FLAVOR_MULTIWORD:
            if mw in cand: notes.add(mw.title())
        for s in FLAVOR_SINGLE:
            if re.search(rf"\b{re.escape(s)}\b", cand): notes.add(s.title())
        return sorted(notes)
    # fallback sweep
    text = " ".join(_as_tokens(lines))
    notes = set()
    for mw in FLAVOR_MULTIWORD:
        if mw in text: notes.add(mw.title())
    for s in FLAVOR_SINGLE:
        if re.search(rf"\b{re.escape(s)}\b", text): notes.add(s.title())
    return sorted(notes)

# ---------- (Optional) Name/roaster detectors (disabled) ----------
def detect_label_name(_: List[str], __: Optional[str]) -> Optional[str]:
    return None  # per requirement, we won't auto-fill name

def detect_roaster(_: List[str]) -> Optional[str]:
    return None  # per requirement, we won't auto-fill roaster

# ---------- Main entry ----------
def extract_fields_from_text(text: str) -> Dict[str, Any]:
    lines = split_lines(text)

    # Origin(s)
    origins = detect_origins(lines)
    origin_primary = origins[0] if origins else None

    # Process (canonical + modifiers)
    proc_info = detect_process(lines)

    # Varieties (+ blend flag)
    var_info = detect_varieties_and_blend(lines)

    # Flavor notes
    flavor_notes = detect_flavor_notes(lines)

    out: Dict[str, Any] = {}
    if origin_primary: out["origin"] = origin_primary
    if origins: out["origin_candidates"] = origins  # safe extra, UI may ignore
    if proc_info.get("process"): out["process"] = proc_info["process"]
    if proc_info.get("process_tags"): out["process_tags"] = proc_info["process_tags"]
    if var_info.get("variety"): out["variety"] = var_info["variety"]
    out["is_blend"] = bool(var_info.get("is_blend"))
    if flavor_notes: out["flavor_notes"] = flavor_notes

    # DO NOT auto-fill roaster or name per your request.

    # Always include raw lines to aid correction
    out["_raw_lines"] = lines
    return out
