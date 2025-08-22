# breau_backend/app/routers/brew.py
from fastapi import APIRouter
from breau_backend.app.schemas import BrewSuggestRequest, BrewSuggestion
from breau_backend.app.services.protocol_generator import build_suggestion


router = APIRouter()

@router.post("/suggest", response_model=BrewSuggestion)
def suggest(req: BrewSuggestRequest) -> BrewSuggestion:
    return build_suggestion(req)
