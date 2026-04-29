import pathlib

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile

from maplerugs.config import settings
from maplerugs.pipeline import RugRecord, process_image

app = FastAPI(title="Maple Rugs Vision Agent")

_ACCEPTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


@app.post("/invocations")
async def invocations(file: UploadFile) -> RugRecord:
    filename = file.filename or ""
    if pathlib.Path(filename).suffix.lower() not in _ACCEPTED_EXTENSIONS:
        raise HTTPException(status_code=422, detail=f"Unsupported file type: {filename}")

    try:
        image_bytes = await file.read()
        return process_image(image_bytes, filename=filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/.well-known/agent.json")
async def agent_card():
    return {
        "name": "Maple Rugs Vision Agent",
        "description": "Analyzes rug images and returns structured descriptions for semantic search indexing.",
        "url": settings.a2a_base_url,
        "version": "0.1.0",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False,
        },
        "defaultInputModes": ["image/png", "image/jpeg", "image/gif", "image/webp"],
        "defaultOutputModes": ["application/json"],
        "skills": [
            {
                "id": "rug-description",
                "name": "Rug Image Description",
                "description": (
                    "Accepts a rug image and returns a structured analysis covering pattern type, "
                    "style, primary and secondary colors, design elements, tone, complexity, "
                    "origin, material, and dimensions."
                ),
                "inputModes": ["image/png", "image/jpeg", "image/gif", "image/webp"],
                "outputModes": ["application/json"],
            }
        ],
    }


@app.get("/ping")
async def ping():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.a2a_host,
        port=settings.a2a_port,
        log_level=settings.log_level.lower(),
    )
