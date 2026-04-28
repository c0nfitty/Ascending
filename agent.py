import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile

from maplerugs.config import settings
from maplerugs.pipeline import RugRecord, process_image

app = FastAPI(title="Maple Rugs Description Agent")


@app.post("/invocations")
async def invocations(file: UploadFile) -> RugRecord:
    if not file.content_type or file.content_type != "image/png":
        raise HTTPException(status_code=422, detail="File must be a PNG image")

    try:
        image_bytes = await file.read()
        return process_image(image_bytes, filename=file.filename or "")
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
