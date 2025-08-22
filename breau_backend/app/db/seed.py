from sqlmodel import Session, select
from .session import engine
from .models import BrewerSpec, FilterSpec, GrinderSpec, WaterProfile

def upsert(session: Session, model, where: dict, values: dict):
    row = session.exec(select(model).filter_by(**where)).first()
    if row:
        for k, v in values.items():
            setattr(row, k, v)
        session.add(row)
        return row
    row = model(**where, **values)
    session.add(row)
    return row

def seed_defaults():
    with Session(engine) as session:
        # Brewers
        upsert(session, BrewerSpec,
               {"name": "Hario V60-02"},
               {"geometry_type": "conical", "cone_angle_deg": 60.0,
                "outlet_profile": "single_large", "size_code": "02",
                "inner_diameter_mm": 115, "thermal_mass": "medium"})
        upsert(session, BrewerSpec,
               {"name": "Kalita Wave 185"},
               {"geometry_type": "flat", "outlet_profile": "multi_small",
                "size_code": "185", "inner_diameter_mm": 95, "thermal_mass": "medium"})

        # Filters
        upsert(session, FilterSpec,
               {"material": "paper_bleached", "permeability": "fast", "thickness": "thin"},
               {"pore_size_microns": 20})
        upsert(session, FilterSpec,
               {"material": "paper_bleached", "permeability": "medium", "thickness": "medium"},
               {"pore_size_microns": 25})
        upsert(session, FilterSpec,
               {"material": "paper_unbleached", "permeability": "slow", "thickness": "thick"},
               {"pore_size_microns": 30})

        # Grinder example
        upsert(session, GrinderSpec,
               {"model": "Timemore Chestnut C3"},
               {"burr_type": "conical", "scale_type": "numbers",
                "user_scale_min": 0, "user_scale_max": 36,
                "calibration_points": {"filter medium-fine": 22}})

        # Water preset (approx. SCA-style)
        upsert(session, WaterProfile,
               {"profile_preset": "sca_target"},
               {"hardness_gh": 70, "alkalinity_kh": 40, "tds": 120,
                "calcium_mg_l": 25, "magnesium_mg_l": 10, "sodium_mg_l": 10, "bicarbonate_mg_l": 50})

        session.commit()
        return "seeded"
