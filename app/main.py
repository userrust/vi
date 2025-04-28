from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
import datetime
from pathlib import Path
from typing import List

# Инициализация приложения
app = FastAPI(title="Video Upload Service", version="1.0")

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Конфигурация
BASE_DIR = Path(__file__).parent.resolve()
STATIC_DIR = BASE_DIR / "static"
VIDEO_DIR = BASE_DIR / "videos"
ALLOWED_EXTENSIONS = {".mp4", ".webm", ".mov"}
MAX_FILE_SIZE_MB = 50

# Создание директорий
VIDEO_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Монтирование статики
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def sanitize_filename(filename: str) -> str:
    """Очистка имени файла от опасных символов"""
    return "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_')).rstrip()


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Главная страница с формой загрузки"""
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/upload_video")
async def upload_video(file: UploadFile = File(...)):
    """Загрузка видео с конвертацией в MP4"""
    try:
        # Проверка размера файла
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

        if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(413, f"File too large. Max size: {MAX_FILE_SIZE_MB}MB")

        # Проверка расширения
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(400, "Unsupported file format")

        # Генерация имени файла
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = sanitize_filename(Path(file.filename).stem)
        filename = f"recording_{timestamp}_{safe_name}.mp4"
        save_path = VIDEO_DIR / filename

        # Сохранение файла
        with open(save_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        logger.info(f"Video saved: {filename} ({file_size / 1024 / 1024:.2f}MB)")
        return {"message":"Video uploaded successfully", "filename":filename}

    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(500, "Video upload failed")


@app.get("/list-videos", response_model=dict)
async def list_videos() -> dict:
    """Список доступных видео"""
    try:
        videos = [f for f in os.listdir(VIDEO_DIR) if f.endswith('.mp4')]
        return {
            "videos":videos,
            "count":len(videos),
            "base_url":"/videos/"
        }
    except Exception as e:
        logger.error(f"List videos error: {str(e)}")
        raise HTTPException(500, "Could not list videos")


@app.get("/videos/{filename}")
async def serve_video(filename: str):
    """Отдача видеофайла"""
    try:
        filepath = VIDEO_DIR / sanitize_filename(filename)

        if not filepath.exists() or not filepath.is_file():
            raise HTTPException(404, "File not found")

        return FileResponse(
            filepath,
            media_type="video/mp4",
            headers={
                "Content-Disposition":f"inline; filename={filepath.name}",
                "Cache-Control":"public, max-age=3600"
            }
        )
    except Exception as e:
        logger.error(f"Video serve error: {str(e)}")
        raise HTTPException(500, "Could not serve video")

# Для конвертации в MP4 можно добавить (требует ffmpeg):
# async def convert_to_mp4(input_path: Path, output_path: Path):
#     ...