from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os
import logging
import datetime
from pathlib import Path

app = FastAPI()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Пути к директориям (используем абсолютные пути)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
VIDEO_DIR = os.path.join(BASE_DIR, "videos")

# Создаем необходимые директории
Path(STATIC_DIR).mkdir(exist_ok=True)
Path(VIDEO_DIR).mkdir(exist_ok=True)

# Монтируем статические файлы
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def read_root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.post("/upload_video")
async def upload_video(file: UploadFile = File(...)):
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(VIDEO_DIR, f"recording_{timestamp}.webm")

        with open(filename, "wb") as f:
            content = await file.read()
            f.write(content)
        print(filename)
        logger.info(f"Video saved: {filename}")
        return JSONResponse(
            content={"message":"Video uploaded successfully"},
            status_code=200
        )
    except Exception as e:
        logger.error(f"Error saving video: {e}")
        return JSONResponse(
            content={"message":"Error uploading video"},
            status_code=500
        )


from fastapi.responses import FileResponse
from fastapi import HTTPException


@app.get("/list-videos")
async def list_videos():
    try:
        videos = [f for f in os.listdir(VIDEO_DIR) if f.endswith('.webm')]
        return {
            "videos":videos,
            "count":len(videos),
            "base_url":"https://vi-vsli.onrender.com/videos/"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/videos/{filename}")
async def serve_video(filename: str):
    # Безопасно соединяем пути
    filepath = os.path.join(VIDEO_DIR, filename)

    # Защита от path traversal атак
    if not os.path.abspath(filepath).startswith(os.path.abspath(VIDEO_DIR)):
        raise HTTPException(status_code=403, detail="Access denied")

    if os.path.exists(filepath):
        return FileResponse(
            filepath,
            media_type="video/webm",
            headers={"Content-Disposition":f"inline; filename={filename}"}
        )

    raise HTTPException(status_code=404, detail="File not found")
