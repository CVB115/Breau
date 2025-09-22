from __future__ import annotations
import os
import sys
import time
import pytest
from fastapi.testclient import TestClient
from breau_backend.app.main import app
from breau_backend.app.services.learning import feedback_flow

# --- Existing client (used for learning tests) ---
@pytest.fixture(scope="session")
def client():
    return TestClient(app)

# --- New: for brew/session tests ---
@pytest.fixture
def session_client(tmp_data_tree):
    """
    Isolated TestClient using the same tmp_data_tree, intended for brew/session tests.
    """
    return TestClient(app)

@pytest.fixture
def now_ms():
    """
    Returns current time in ms for timestamping pours.
    """
    return lambda: int(time.time() * 1000)

# --- Data tree override (already present, reused by both clients) ---
@pytest.fixture(scope="session", autouse=True)
def tmp_data_tree(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("data_tree")
    os.environ["DATA_DIR"] = str(tmp)
    return tmp

# --- Global learning flag overrides ---
@pytest.fixture(scope="session", autouse=True)
def set_global_flags():
    os.environ["LEARNING_THRESHOLD"] = "3"
    os.environ["BREAU_LEARNING_THRESHOLD"] = "3"
    os.environ["BREAU_BANDIT_WARMUP"] = "3"

# --- Used by overlays / learning tests ---
@pytest.fixture
def sample_flags():
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
    from importlib import reload
    import breau_backend.app.services.learning.overlays as overlays_module

    def _reload():
        return reload(overlays_module)
    return _reload

# --- Used by overlays fakes ---
@pytest.fixture
def user_id():
    return "user_fake"

@pytest.fixture
def goal_tags():
    return ["clarity"]

@pytest.fixture(autouse=True)
def reset_inproc_feedback_counts():
    feedback_flow._INPROC_COUNTS.clear()
