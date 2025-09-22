# app/routers/nlp.py
from fastapi import APIRouter
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer, util
from typing import List, Union
import re

router = APIRouter(prefix="/nlp", tags=["nlp"])

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

INTENTS = [
    "start", "pause", "resume", "next", "finish",
    "add pour", "set water to X grams", "target total X grams",
    "style center", "style spiral", "style pulse",
    "start bloom at T", "start pour 1 at T",
    "remaining water this pour", "dump remaining in last pour"
]
EMBEDS = model.encode(INTENTS, convert_to_tensor=True)

class NLPInput(BaseModel):
    text: str

class LocalEvent(BaseModel):
    type: str
    field: Union[str, None] = None
    value: Union[int, str, None] = None
    action: Union[str, None] = None
    kind: Union[str, None] = None

@router.post("/interpret")
async def interpret_text(body: NLPInput) -> List[LocalEvent]:
    text = body.text.strip().lower()
    if not text:
        return [{"type": "note", "text": "(empty)"}]

    # ---------- helpers ----------
    NUM = {
        "zero":0,"oh":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,
        "ten":10,"eleven":11,"twelve":12,"thirteen":13,"fourteen":14,"fifteen":15,"sixteen":16,
        "seventeen":17,"eighteen":18,"nineteen":19,"twenty":20,"thirty":30,"forty":40,"fifty":50,"sixty":60,
        "seventy":70,"eighty":80,"ninety":90
    }
    ORD = {"first":1,"second":2,"third":3,"fourth":4,"fifth":5}

    def parse_number_wordish(s: str) -> int | None:
        s = s.strip()
        if re.fullmatch(r"\d+", s): return int(s)
        if s in NUM: return NUM[s]
        if "-" in s:
            a,b = s.split("-",1)
            if a in NUM and b in NUM: return NUM[a]+NUM[b]
        if " " in s:
            a,b,*_ = s.split()
            if a in NUM and b in NUM: return NUM[a]+NUM[b]
        return None

    def parse_time_ms(s: str) -> int | None:
        # mm:ss
        m = re.search(r"\b(\d{1,2}):([0-5]\d)\b", s)
        if m: return (int(m.group(1))*60 + int(m.group(2)))*1000
        # X seconds
        m = re.search(r"\b(\d{1,3})\s*s(ec|econd)?s?\b", s)
        if m: return int(m.group(1))*1000
        # "0 forty" / "one oh five"
        toks = [t for t in re.sub(r"[^a-z0-9\s\-]", " ", s).split() if t]
        # detect patterns like ["0","forty"] or ["one","oh","five"]
        if len(toks) >= 2:
            if toks[0] in {"0","zero","oh"}:
                sec = parse_number_wordish(toks[1])
                if sec is not None and 0 <= sec < 60: return sec*1000
            # "one oh five" → 1:05
            a = parse_number_wordish(toks[0]); b = parse_number_wordish(toks[2] if len(toks)>=3 and toks[1] in {"oh","0","zero"} else toks[1])
            if a is not None and b is not None and 0 <= b < 60:
                return (a*60 + b)*1000
        return None

    def parse_pour_idx(s: str) -> int | None:
        # robust to "pour two" and misheard "for two"
        m = re.search(r"\b(pour|for)\s+(first|second|third|fourth|fifth|\d+)\b", s)
        if not m: return None
        tok = m.group(2)
        return (ORD.get(tok) or int(tok)) - 1

    def parse_target(s: str):
        # accept “bloom” anywhere, not only “in bloom”
        if re.search(r"\bbloom\b", s):
            return {"kind":"bloom"}
        idx = parse_pour_idx(s)
        if idx is not None:
            return {"kind":"pour","idx":idx}
        return None

    def grams_in(s: str) -> int | None:
        m = re.search(r"\b(\d{1,3})\b", s)
        if m: return int(m.group(1))
        # number words
        words = s.replace("-", " ").split()
        vals = [parse_number_wordish(w) for w in words]
        vals = [v for v in vals if v is not None]
        if vals: return vals[-1]
        return None

    # split multi-intents
    clauses = re.split(r"\s+\b(?:and|then)\b\s+", text)
    raw_events: list[dict] = []

    for clause in clauses:
        clause = clause.strip()
        if not clause: continue

        # MiniLM intent gate
        q = model.encode(clause, convert_to_tensor=True)
        sim = util.cos_sim(q, EMBEDS)[0]
        idx = int(sim.argmax()); score = float(sim[idx]); intent = INTENTS[idx] if score >= 0.55 else ""
        tgt = parse_target(clause)

        # pattern fallbacks for low-confidence but obvious commands
        if not intent:
            if re.search(r"\bset\s+water\b", clause): intent = "set water to X grams"
            elif re.search(r"\btarget\s+total\b", clause): intent = "target total X grams"
            elif re.search(r"\bdump\b.*\bremaining\b.*\blast\b.*\bpour\b", clause): intent = "dump remaining in last pour"
            elif re.search(r"\bremaining\b.*\bthis\b.*\bpour\b", clause): intent = "remaining water this pour"
            elif re.search(r"\bstart\b.*\bbloom\b", clause): intent = "start bloom at T"
            elif re.search(r"\bstart\b.*\bpour\b", clause): intent = "start pour 1 at T"

        # map intents to events
        if intent in {"start","pause","resume","next","finish"}:
            raw_events.append({"type":"control","action":intent}); continue
        if intent == "add pour":
            raw_events.append({"type":"add_pour"}); continue
        if intent == "dump remaining in last pour":
            raw_events.append({"type":"dump_last"}); continue
        if intent == "remaining water this pour":
            raw_events.append({"type":"dump_here"}); continue
        if intent.startswith("style"):
            style = intent.split(" ")[1]
            ev = {"type":"set_field","field":"pour_style","value":style}
            if tgt: ev["target"] = tgt
            raw_events.append(ev); continue
        if "target total" in intent or "target total" in clause:
            g = grams_in(clause)
            if g is not None: raw_events.append({"type":"set_target","grams":g}); continue
        if "set water" in intent or re.search(r"\bset\s+water\b", clause):
            g = grams_in(clause)
            if g is not None:
                ev = {"type":"set_field","field":"water_g","value":g}
                if tgt: ev["target"] = tgt
                raw_events.append(ev); continue
        if "start bloom" in intent or re.search(r"\bstart\b.*\bbloom\b", clause):
            ms = parse_time_ms(clause)
            raw_events.append({"type":"control_step","action":"start","kind":"bloom"})
            if ms is not None:
                ev = {"type":"set_field","field":"plan_start_ms","value":ms,"target":{"kind":"bloom"}}
                raw_events.append(ev)
            continue
        if "start pour" in intent or re.search(r"\bstart\b.*\bpour\b", clause):
            idx = parse_pour_idx(clause) or 0
            ms = parse_time_ms(clause)
            raw_events.append({"type":"control_step","action":"start","kind":"pour","idx":idx})
            if ms is not None:
                ev = {"type":"set_field","field":"plan_start_ms","value":ms,"target":{"kind":"pour","idx":idx}}
                raw_events.append(ev)
            continue
        if re.search(r"\b(end|finish)\b", clause):
            ms = parse_time_ms(clause)
            raw_events.append({"type":"control_step","action":"end","kind": (tgt["kind"] if tgt else None), "idx": (tgt.get("idx") if tgt else None)})
            if ms is not None:
                ev = {"type":"set_field","field":"plan_end_ms","value":ms}
                if tgt: ev["target"] = tgt
                raw_events.append(ev)
            continue

        # fallback: note
        raw_events.append({"type":"note","text":clause})

    # enforce stable ordering inside one utterance:
    # values/targets first, then step controls, then high-level controls
    priority = {"set_field":0, "set_target":0, "add_pour":1, "control_step":2, "dump_here":2, "dump_last":2, "control":3, "note":4}
    raw_events.sort(key=lambda e: priority.get(e.get("type","note"), 5))
    return raw_events if raw_events else [{"type":"note","text":text}]
