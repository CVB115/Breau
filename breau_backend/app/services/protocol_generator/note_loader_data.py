# breau_backend/app/services/protocol_generator/note_loader_data.py
"""
Minimal prior data so imports in note_loader.py / suggest_profile.py succeed.
Extend this later with your full curated priors.
"""

# Simple cluster → default notes mapping (placeholder but realistic)
PRIOR_NOTES_BY_CLUSTER = {
    "clarity": [
        "jasmine", "lemon", "bergamot", "orange_blossom", "green_grape"
    ],
    "body": [
        "molasses", "cocoa", "prune", "toffee", "dark_chocolate"
    ],
    # fallback
    "default": [
        "red_grape", "plum", "candied_orange", "lychee", "cranberry"
    ],
}

def get_cluster_notes(cluster: str):
    """Return a non-empty list for any cluster."""
    return PRIOR_NOTES_BY_CLUSTER.get(cluster) or PRIOR_NOTES_BY_CLUSTER["default"]

# Optional metadata hook if other loaders check for it
SCHEMA_VERSION = "2025-09-10"
