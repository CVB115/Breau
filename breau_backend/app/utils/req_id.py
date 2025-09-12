# breau_backend/app/utils/req_id.py
from __future__ import annotations
import os, time

def new_request_id(prefix: str = "req") -> str:
    return f"{prefix}-{int(time.time()*1000)}-{os.getpid()}"
