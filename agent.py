import pathlib

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile

from maplerugs.config import settings
from maplerugs.pipeline import RugRecord, process_image

app = FastAPI(title="Maple Rugs Description Agent")

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
