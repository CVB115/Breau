# breau_backend/app/protocol_generator/parser.py
from __future__ import annotations
from typing import List, Tuple

AGI_ORDER = ["none", "gentle", "moderate", "high"]

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def parse_ratio_den(ratio: str) -> float:
    try:
        _, rhs = ratio.split(":")
        return float(rhs)
    except Exception:
        return 15.0

def format_ratio_den(n: float) -> str:
    n = round(n, 1)
    return f"1:{int(n)}" if float(n).is_integer() else f"1:{n}"

def _agi_index(a: str) -> int:
    try:
        return AGI_ORDER.index(a)
    except ValueError:
        return 1  # default "gentle"

def reduce_late_agitation(pours: List[dict]) -> None:
    if not pours:
        return
    last = pours[-1]
    idx = _agi_index(last.get("agitation", "gentle"))
    if idx > 0:
        last["agitation"] = AGI_ORDER[idx - 1]

def increase_mid_agitation(pours: List[dict]) -> None:
    if not pours:
        return
    mid_i = len(pours) // 2
    idx = _agi_index(pours[mid_i].get("agitation", "gentle"))
    if idx < len(AGI_ORDER) - 1:
        pours[mid_i]["agitation"] = AGI_ORDER[idx + 1]

def bounded_nudges(
    goals: List[str],
    temp_c: float,
    ratio_den: float,
    drawdown_s: int,
    pours: List[dict],
) -> Tuple[float, float, int, List[dict], bool, bool]:
    temp_delta = 0.0
    den_delta = 0.0
    dd_delta = 0.0
    want_reduce_late = False
    want_bump_mid = False

    for phrase in goals:
        if phrase == "increase florality":
            temp_delta += -1.0
            dd_delta += -5.0
        elif phrase == "reduce florality":
            temp_delta += +0.5
            dd_delta += +5.0
        elif phrase == "increase body":
            temp_delta += +1.0
            den_delta += -0.5
            dd_delta += +10.0
            want_bump_mid = True
        elif phrase == "reduce body":
            temp_delta += -0.5
            den_delta += +0.5
            dd_delta += -10.0
            want_reduce_late = True
        elif phrase == "increase sweetness":
            temp_delta += +0.5
            dd_delta += +5.0
        elif phrase == "reduce sweetness":
            temp_delta += -0.5
            dd_delta += -5.0
        elif phrase == "increase acidity":
            temp_delta += -0.75
            dd_delta += -5.0
        elif phrase == "reduce acidity":
            temp_delta += +0.5
            dd_delta += +5.0
        elif phrase == "reduce bitterness":
            temp_delta += -1.0
            den_delta += +0.2
            dd_delta += -10.0
            want_reduce_late = True
        elif phrase == "increase bitterness":
            temp_delta += +0.5
            den_delta += -0.2
            dd_delta += +5.0

    base_t = float(temp_c)
    temp_c = int(round(clamp(base_t + temp_delta, base_t - 2.0, base_t + 2.0)))
    ratio_den = clamp(ratio_den + den_delta, 12.0, 18.0)
    base_dd = float(drawdown_s)
    drawdown_s = int(round(clamp(base_dd + dd_delta, base_dd - 20.0, base_dd + 20.0)))

    if want_reduce_late:
        reduce_late_agitation(pours)
    if want_bump_mid:
        increase_mid_agitation(pours)

    return temp_c, ratio_den, drawdown_s, pours, want_reduce_late, want_bump_mid

def build_description(
    goals: List[str],
    temp_c: int,
    ratio: str,
    agitation_summary: str,
) -> str:
    bits: List[str] = []
    if "increase florality" in goals:
        bits.append("cooler water and a slightly higher ratio to preserve delicate volatiles")
    if "reduce body" in goals:
        bits.append("gentler late agitation to keep the cup lighter")
    if "increase body" in goals:
        bits.append("a touch more heat and mid‑pour agitation for a syrupier mouthfeel")
    if "increase sweetness" in goals:
        bits.append("warmer water to round out sugars")
    if "reduce bitterness" in goals:
        bits.append("slightly cooler water to soften bittering compounds")
    if not bits:
        bits.append("balanced settings targeting clarity without over‑extraction")

    return (
        f"Set temperature {temp_c}°C, ratio {ratio}, {agitation_summary}. "
        f"This aligns with {'; '.join(bits)}."
    )
