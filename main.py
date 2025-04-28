from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import List
import logging
import time
from uuid import uuid4

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Модуль для управления потоками
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.streamers: dict = {}  # Словарь для хранения активных стримеров по их id
        self.last_data_time = {}

    async def connect(self, websocket: WebSocket, streamer_id: str = None):
        await websocket.accept()
        if streamer_id:
            self.streamers[streamer_id] = websocket  # Добавляем стримера
            logger.info(f"Streamer {streamer_id} connected")
        else:
            self.active_connections.append(websocket)
            logger.info(f"New viewer connected. Total viewers: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket, streamer_id: str = None):
        if streamer_id:
            del self.streamers[streamer_id]  # Удаляем стримера
            logger.info(f"Streamer {streamer_id} disconnected")
        else:
            self.active_connections.remove(websocket)
            logger.info(f"Viewer disconnected. Remaining viewers: {len(self.active_connections)}")

    async def broadcast(self, data: bytes, streamer_id: str):
        if streamer_id in self.streamers:
            await self.streamers[streamer_id].send_bytes(data)

    def is_stream_active(self, streamer_id: str):
        return streamer_id in self.streamers


manager = ConnectionManager()


@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request":request})


@app.get("/streams", response_class=HTMLResponse)
async def show_streams(request: Request):
    return templates.TemplateResponse("streams.html", {"request":request})


@app.websocket("/ws/stream/{streamer_id}")
async def websocket_stream(websocket: WebSocket, streamer_id: str):
    await manager.connect(websocket, streamer_id)
    try:
        while True:
            data = await websocket.receive_bytes()
            if len(data) == 0:
                logger.warning("Received empty data packet")
                continue

            logger.debug(f"Received {len(data)} bytes from streamer {streamer_id}")
            await manager.broadcast(data, streamer_id)

    except WebSocketDisconnect as e:
        logger.info(f"Streamer {streamer_id} disconnected: {e}")
        manager.disconnect(websocket, streamer_id)
    except Exception as e:
        logger.error(f"Streamer {streamer_id} error: {e}")
        manager.disconnect(websocket, streamer_id)


@app.websocket("/ws/watch")
async def websocket_watch(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        logger.info("Viewer disconnected")
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Viewer error: {e}")
        manager.disconnect(websocket)


@app.on_event("startup")
async def startup():
    logger.info("Streaming server started")


@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down streaming server")
    for streamer_id, connection in manager.streamers.copy().items():
        await connection.close(code=1001, reason="Server shutdown")
    for connection in manager.active_connections.copy():
        await connection.close(code=1001, reason="Server shutdown")
