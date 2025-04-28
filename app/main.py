from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import logging
import datetime
from pathlib import Path
import os

app = FastAPI()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создаем папку для сохранения видео
VIDEO_DIR = os.path.join(os.path.dirname(__file__), "videos")
Path(VIDEO_DIR).mkdir(exist_ok=True)

# Монтируем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def get_index():
    return FileResponse(os.path.join("static", "index.html"))


@app.post("/upload_video")
async def upload_video(file: UploadFile = File(...)):
    try:
        # Генерируем уникальное имя файла
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(VIDEO_DIR, f"recording_{timestamp}.webm")

        # Сохраняем полученное видео
        with open(filename, "wb") as f:
            content = await file.read()
            f.write(content)

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


@app.on_event("startup")
async def startup():
    logger.info("Server started")


@app.on_event("shutdown")
async def shutdown():
    logger.info("Server stopped")
