# breau_backend/app/services/data_stores/__init__.py
"""
Unified export surface for data store helpers.

Import from here in routers/engine code, e.g.:
    from breau_backend.app.services.data_stores import (
        # IO
        read_json, atomic_write, append_jsonl,
        # Profiles
        PROFILES_PATH, get_profile, upsert_profile,
        resolve_defaults_for_request, get_default_profile_template,
        # Feedback
        append_feedback, list_feedback,
        # Sessions
        append_session, list_sessions,
        # Beans
        BEANS_PATH, list_beans, create_bean, update_bean, get_bean_by_alias,
    )
"""

from __future__ import annotations

# ---- Low-level IO helpers ----
from .io_utils import read_json, atomic_write, append_jsonl  # noqa: F401

# ---- Profiles store (note: no delete_profile export) ----
from .profiles import (  # noqa: F401
    PROFILES_PATH,
    get_profile,
    upsert_profile,
    resolve_defaults_for_request,
    get_default_profile_template,
)

# ---- Feedback store ----
from .feedback import (  # noqa: F401
    append_feedback,
    list_feedback,
)

# ---- Sessions store ----
from .sessions import (  # noqa: F401
    append_session,
    list_sessions,
)

# ---- Beans store ----
from .beans import (  # noqa: F401
    BEANS_PATH,
    list_beans,
    create_bean,
    update_bean,
    get_bean_by_alias,
)

__all__ = [
    # io_utils
    "read_json", "atomic_write", "append_jsonl",
    # profiles
    "PROFILES_PATH", "get_profile", "upsert_profile",
    "resolve_defaults_for_request", "get_default_profile_template",
    # feedback
    "append_feedback", "list_feedback",
    # sessions
    "append_session", "list_sessions",
    # beans
    "BEANS_PATH", "list_beans", "create_bean", "update_bean", "get_bean_by_alias",
]
