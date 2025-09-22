# app/routers/voice.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from faster_whisper import WhisperModel
import tempfile, os

router = APIRouter(prefix="/voice", tags=["voice"])

model_size = os.getenv("STT_MODEL", "tiny")
model = WhisperModel(model_size, device="cpu", compute_type="int8")

@router.post("/chunk")
async def transcribe_chunk(file: UploadFile = File(...)):
    try:
        with tempfile.NamedTemporaryFile(delete=True, suffix=".wav") as tmp:
            tmp.write(await file.read())
            tmp.flush()
            segments, info = model.transcribe(tmp.name, beam_size=5)
            text = " ".join(seg.text.strip() for seg in segments if seg.text.strip())
            return {
                "text": text,
                "t0_ms": 0,
                "t1_ms": int(info.duration * 1000),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"transcription error: {e}")
