# breau_backend/app/protocol_generator/__init__.py
from .builder import build_suggestion
from .note_loader import blend_predicted_notes  # re-export tolerant version

__all__ = ["blend_predicted_notes", "build_suggestion"]