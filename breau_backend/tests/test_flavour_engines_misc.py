# tests/test_flavour_engines_misc.py
from pathlib import Path
import textwrap, json, yaml

from breau_backend.app.flavour.engine.grind_math import microns_for_setting, microns_for_setting_grinder, setting_for_microns_grinder
from breau_backend.app.flavour.engine.taxonomy import TagTaxonomy, load_taxonomy
from breau_backend.app.flavour.engine.nudger import Nudger

# Purpose:
# Cover grind mapping, taxonomy validation, and nudger policy flow.

def test_grind_math_preset_and_inverse():
    # preset model
    g = {"model": "Comandante C40"}
    m = microns_for_setting_grinder(g, 10)
    assert 150 <= m <= 1400
    # inverse mapping (clamps & rounds safely)
    s = setting_for_microns_grinder(g, m)
    assert isinstance(s, (int, float))

def test_taxonomy_loading_and_validation(tmp_path):
    yml = textwrap.dedent("""
    facets:
      aroma: [floral, citrus]
      mouthfeel: [silky, syrupy]
    aliases:
      floral: [flower, blossom]
    """).strip()
    p = tmp_path / "taxonomy.yaml"
    p.write_text(yml, encoding="utf-8")
    tx = load_taxonomy(p)
    ok, msg = tx.validate_tag("aroma:floral")
    assert ok
    bad, msg = tx.validate_tag("wrong")
    assert not bad

def test_nudger_policy_linear_and_clips():
    policy = {
        "goal_variable_matrix": {
            "clarity": {"slurry_c": -1.0, "agitation_early": -1.0},
            "body":    {"slurry_c": +1.0, "agitation_late": +1.0},
        },
        "caps": {"delta_slurry_c_per_session": 0.5, "delta_ratio_den_per_session": 0.5, "agitation_step_per_session": 1},
        "constraints": {
            "conical": {"slurry_c_min": 85.0, "slurry_c_max": 98.0, "ratio_den_min": 12, "ratio_den_max": 20},
        },
    }
    n = Nudger(policy)
    base = {"slurry_c": 92.0, "ratio_den": 15, "agitation": "medium"}
    delta, reasons = n.propose({"clarity": 1.0, "body": 0.0}, base, {}, {})
    assert "clarity" in " ".join(reasons)
    final, clips = n.apply_and_clip(base, delta, {"brewer": {"geometry_type": "conical"}})
    assert 85.0 <= final["slurry_c"] <= 98.0
