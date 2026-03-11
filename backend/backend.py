"""
AutoGraph API
=============
Two endpoints:
  POST /generate        – text  → Mermaid (qwen3-32b via text_service)
  POST /generate-image  – image → Mermaid (gemini-2.0-flash via vision_service)
"""

import logging
import os

import dotenv
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from text_service import generate_from_text
from vision_service import generate_from_image, mime_from_filename

dotenv.load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AutoGraph")

app = FastAPI(title="AutoGraph API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VALID_ORIENTATIONS = {"TD", "TB", "LR", "RL", "BT"}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class FlowchartRequest(BaseModel):
    text: str
    orientation: str = "TD"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_groq_key() -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not set in .env file")
    return api_key


def _check_gemini_key() -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not set in .env file")
    return api_key


def _normalise_orientation(raw: str) -> str:
    o = raw.upper()
    return o if o in VALID_ORIENTATIONS else "TD"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/generate")
def generate_text_endpoint(request: FlowchartRequest):
    """Convert a natural-language process description into a Mermaid diagram."""
    _check_groq_key()
    orientation = _normalise_orientation(request.orientation)
    try:
        result = generate_from_text(request.text, orientation)
        return result
    except Exception as e:
        logger.error(f"[/generate] {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-image")
async def generate_image_endpoint(
    image: UploadFile = File(..., description="Flowchart image (PNG / JPG / WEBP / GIF)"),
    orientation: str = Form("TD", description="Graph orientation: TD | LR | TB | RL | BT"),
):
    """Convert a flowchart image into a Mermaid diagram."""
    _check_gemini_key()
    orientation = _normalise_orientation(orientation)

    try:
        mime_type = mime_from_filename(image.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    logger.info(
        f"[/generate-image] file={image.filename!r} "
        f"mime={mime_type} size={len(image_bytes)} orientation={orientation}"
    )

    try:
        result = generate_from_image(image_bytes, mime_type, orientation)
        return result
    except Exception as e:
        logger.error(f"[/generate-image] {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5000)