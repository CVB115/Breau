import pytest
from breau_backend.app.services.nlp.text_to_goals import parse_text_to_goals

def _as_dir_set(goals):
    return {(g["trait"], g["direction"]) for g in goals}

def test_bright_clean_less_bitter():
    g = parse_text_to_goals("brighter, cleaner, less bitter")
    s = _as_dir_set(g)
    assert ("clarity", "increase") in s
    assert ("acidity", "increase") in s
    assert ("bitterness", "decrease") in s

def test_fuller_sweeter_not_bitter():
    g = parse_text_to_goals("fuller body, sweeter, not bitter")
    s = _as_dir_set(g)
    assert ("body", "increase") in s
    assert ("sweetness", "increase") in s
    assert ("bitterness", "decrease") in s

def test_conflicting_intents_net_out():
    g = parse_text_to_goals("more clarity but less body, reduce bitterness")
    s = _as_dir_set(g)
    assert ("clarity", "increase") in s
    assert ("body", "decrease") in s
    assert ("bitterness", "decrease") in s

def test_empty_text_gives_no_goals():
    assert parse_text_to_goals("") == []
