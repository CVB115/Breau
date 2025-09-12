from __future__ import annotations
import os
import sys
import pathlib
import pytest
from fastapi.testclient import TestClient
from breau_backend.app.services.learning import feedback_flow

@pytest.fixture(scope="session")
def client():
    from breau_backend.app.main import app
    return TestClient(app)

@pytest.fixture
def sample_flags():
    # used by overlays test
    return {
        "use_learned_edges": False,
        "use_user_personalisation": True,
        "use_practice": False,
        "use_curriculum": False,
        "use_model_planner": False,
        "use_cohort_seed": False,
    }

@pytest.fixture
def reload_overlays():
    """
    Return a callable; when invoked, it reloads and returns the overlays module.
    """
    from importlib import reload
    import breau_backend.app.services.learning.overlays as overlays_module

    def _reload():
        return reload(overlays_module)
    return _reload

@pytest.fixture(scope="session", autouse=True)
def set_global_flags():
    """
    Tests post 3 feedback events then expect learning mode == 'ON'.
    Make that explicit via environment so Evaluator/Bandit warmup reads 3.
    """
    os.environ["LEARNING_THRESHOLD"] = "3"
    os.environ["BREAU_LEARNING_THRESHOLD"] = "3"
    os.environ["BREAU_BANDIT_WARMUP"] = "3"

@pytest.fixture(scope="session", autouse=True)
def tmp_data_tree(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("data_tree")
    os.environ["DATA_DIR"] = str(tmp)
    return tmp

# --- fixtures required by test_overlays_with_fakes.py ---
@pytest.fixture
def user_id():
    return "user_fake"

@pytest.fixture
def goal_tags():
    return ["clarity"]

@pytest.fixture(autouse=True)
def reset_inproc_feedback_counts():
    feedback_flow._INPROC_COUNTS.clear()