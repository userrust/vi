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
