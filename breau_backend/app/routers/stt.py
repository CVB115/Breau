# app/routers/stt.py
from __future__ import annotations

import os, re, json, tempfile, shutil
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

router = APIRouter(prefix="/stt", tags=["stt"])

# ------------------------- Utils: number words → int -------------------------
_NUMS_0_19 = {
    "zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,
    "ten":10,"eleven":11,"twelve":12,"thirteen":13,"fourteen":14,"fifteen":15,
    "sixteen":16,"seventeen":17,"eighteen":18,"nineteen":19
}
_TENS = {"twenty":20,"thirty":30,"forty":40,"fifty":50,"sixty":60,"seventy":70,"eighty":80,"ninety":90}
_SCALES = {"hundred":100}

def _wordnum_to_int(words: List[str]) -> Optional[int]:
    """
    Parse small English quantities like 'ninety six', 'one hundred', 'two hundred five'.
    Returns None if it doesn't look like a number phrase.
    """
    if not words: return None
    total = 0
    current = 0
    found = False
    for w in words:
        w = w.lower()
        if w in _NUMS_0_19:
            current += _NUMS_0_19[w]; found = True
        elif w in _TENS:
            current += _TENS[w]; found = True
        elif w in _SCALES:
            if current == 0: current = 1
            current *= _SCALES[w]; found = True
        elif w in ("and","a"):
            continue
        else:
            # stop at first unknown
            break
    total += current
    return total if found else None

def _extract_first_number(text: str) -> Optional[float]:
    """
    Find the first numeric value either as digits (e.g., 120 / 96.5) or as number words.
    """
    # digits
    m = re.search(r"(?<![\d.])(\d+(?:\.\d+)?)(?![\d.])", text)
    if m:
        try: return float(m.group(1))
        except: pass
    # number words (up to three tokens)
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    for i in range(len(tokens)):
        for j in range(min(3, len(tokens)-i), 0, -1):
            n = _wordnum_to_int(tokens[i:i+j])
            if n is not None:
                return float(n)
    return None

# ------------------------- NLP Parsing -------------------------
_STYLE_ALIASES = {
    "straight":"center", "centre":"center", "center":"center", "central":"center", "centered":"center",
    "spiral":"spiral", "swirl":"spiral", "circle":"spiral", "circular":"spiral",
    "pulse":"pulse", "pulses":"pulse", "pulsed":"pulse",
}
_INTENSITY_ALIASES = {
    "gentle":"gentle", "light":"gentle", "slight":"gentle",
    "moderate":"moderate", "medium":"moderate",
    "high":"high", "strong":"high", "hard":"high", "vigorous":"high", "robust":"high",
}

def _parse_fields(nl: str) -> Tuple[Dict[str, Any], float, List[str]]:
    """
    Very tolerant parser for manual brew phrases.
    Returns (fields, confidence, ambiguous_keys).
    fields: {water_to, temp_C, pour_style, agitation{method,intensity}, pulse_count?}
    """
    text = " ".join(nl.strip().split())
    lower = text.lower()
    fields: Dict[str, Any] = {}
    ambiguous: List[str] = []

    # --- water target (to X / water to X / pour to X / 'to one twenty grams') ---
    m = re.search(r"(?:water\s+to|pour\s+to|to)\s+(\d+(?:\.\d+)?)\s*(?:g|grams?)?", lower)
    if m:
        fields["water_to"] = float(m.group(1))
    else:
        # fallback: any "[X] grams" or bare number if context mentions water/pour
        m2 = re.search(r"(\d+(?:\.\d+)?)\s*(?:g|grams?)\b", lower)
        if m2: fields["water_to"] = float(m2.group(1))
        elif any(k in lower for k in ("water","pour")):
            n = _extract_first_number(lower)
            if n is not None: fields["water_to"] = float(n)

    # --- temperature (at X degrees / temp X / X C) ---
    # digits case
    m = re.search(r"(?:temp(?:erature)?\s*|at\s+)?(\d{2,3})(?:\s*°?\s*c|(?:\s*degrees?\s*c)?|\s*degrees?)\b", lower)
    if m:
        temp = int(m.group(1))
        if 70 <= temp <= 100: fields["temp_C"] = temp
    else:
        # number words near 'degree' / 'temp'
        m2 = re.search(r"(?:temp(?:erature)?|at)\s+([a-z -]+?)\s*(?:degrees?|°?\s*c)\b", lower)
        if m2:
            n = _wordnum_to_int(re.findall(r"[a-z]+", m2.group(1)))
            if isinstance(n, int) and 70 <= n <= 100:
                fields["temp_C"] = n

    # --- pour style (center/straight/spiral/pulse) + pulse count like 'two pulses' ---
    for k, norm in _STYLE_ALIASES.items():
        if re.search(rf"\b{k}\b", lower):
            fields["pour_style"] = norm
            if norm == "pulse":
                # capture count if present
                mcount = re.search(r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+pulse", lower)
                if mcount:
                    raw = mcount.group(1)
                    try:
                        fields["pulse_count"] = int(raw)
                    except:
                        n = _wordnum_to_int([raw])
                        if n: fields["pulse_count"] = int(n)
            break

    # --- agitation (stir, swirl, spin, shake) + intensity ---
    method = None
    if re.search(r"\bstir(ring)?\b", lower): method = "stir"
    elif re.search(r"\bswirl(ing)?\b", lower): method = "swirl"
    elif re.search(r"\bspin(ning)?\b", lower): method = "spin"
    elif re.search(r"\bshake|agitate|agitation|swish|wiggle|tap\b", lower): method = "shake"
    if method:
        intensity = None
        for word, norm in _INTENSITY_ALIASES.items():
            if re.search(rf"\b{word}\b", lower):
                intensity = norm; break
        fields["agitation"] = {"method": method, **({"intensity": intensity} if intensity else {})}

    # crude confidence: 0.5 base + 0.1 per field
    conf = min(0.5 + 0.1 * len(fields.keys()), 0.95)
    if "pour_style" in fields and fields["pour_style"] == "pulse" and "pulse_count" not in fields:
        ambiguous.append("pulse_count")

    return fields, conf, ambiguous

# ------------------------- Optional Whisper/Faster-Whisper -------------------------
def _transcribe_tmp(tmp_path: str, lang: Optional[str]) -> str:
    """
    Try whisper / faster-whisper if available; otherwise return empty text.
    """
    # faster-whisper
    try:
        from faster_whisper import WhisperModel  # type: ignore
        model_size = os.getenv("STT_MODEL", "tiny")
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(tmp_path, language=lang or "en", vad_filter=True)
        return " ".join(seg.text.strip() for seg in segments if getattr(seg, "text", "").strip())
    except Exception:
        pass
    # openai-whisper
    try:
        import whisper  # type: ignore
        model_size = os.getenv("STT_MODEL", "tiny")
        model = whisper.load_model(model_size)
        result = model.transcribe(tmp_path, language=lang or "en")
        return str(result.get("text") or "").strip()
    except Exception:
        pass
    return ""  # best-effort; FE can pass text_override during dev

# ------------------------- Route -------------------------
@router.post("/recognize")
async def recognize(
    audio: UploadFile | None = File(default=None),
    mode: str = Form(default="manual_log"),
    card: str = Form(default="pour"),
    lang: str = Form(default="en"),
    text_override: str = Form(default=""),
    hints: str = Form(default=""),   # JSON array of hint strings (optional)
):
    """
    Accepts a short audio clip and returns {text, fields, confidence, ambiguous}.
    Privacy: the uploaded audio is deleted immediately after transcription.
    Dev: if you pass text_override, we skip STT and just parse that text.
    """
    # decode hints (not used in this simple parser, but reserved for future custom prompts)
    try:
        if hints:
            json.loads(hints)
    except Exception:
        pass

    tmpdir = tempfile.mkdtemp(prefix="stt_tmp_")
    tmp_path = ""
    try:
        if text_override.strip():
            text = text_override.strip()
        elif audio is not None:
            # save to tmp
            suffix = Path(audio.filename or "").suffix or ".webm"
            tmp_path = str(Path(tmpdir) / f"audio{suffix}")
            with open(tmp_path, "wb") as f:
                while True:
                    chunk = await audio.read(1024 * 1024)
                    if not chunk: break
                    f.write(chunk)
            text = _transcribe_tmp(tmp_path, lang)
        else:
            raise HTTPException(status_code=400, detail="missing audio or text_override")

        fields, conf, ambiguous = _parse_fields(text)

        return {
            "text": text,
            "fields": fields,
            "confidence": conf,
            "ambiguous": ambiguous,
            "card": card,
            "mode": mode,
        }
    finally:
        # delete temp audio and folder (privacy)
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass
