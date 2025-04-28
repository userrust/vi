from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import List
import logging
import time

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.streamer_connection = None
        self.last_data_time = 0

    async def connect(self, websocket: WebSocket, is_streamer: bool):
        await websocket.accept()
        if is_streamer:
            if self.streamer_connection:
                await self.streamer_connection.close(code=1001, reason="New streamer connected")
            self.streamer_connection = websocket
            logger.info("New streamer connected")
        else:
            self.active_connections.append(websocket)
            logger.info(f"New viewer connected. Total viewers: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket == self.streamer_connection:
            self.streamer_connection = None
            logger.info("Streamer disconnected")
        else:
            self.active_connections.remove(websocket)
            logger.info(f"Viewer disconnected. Remaining viewers: {len(self.active_connections)}")

    async def broadcast(self, data: bytes):
        self.last_data_time = time.time()
        if not self.active_connections:
            return

        # Оптимизация: отправляем только если есть подключенные зрители
        for connection in self.active_connections.copy():
            try:
                await connection.send_bytes(data)
            except Exception as e:
                logger.error(f"Error sending to viewer: {e}")
                self.disconnect(connection)

    def is_stream_active(self):
        return self.streamer_connection is not None


manager = ConnectionManager()


@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request":request})


@app.get("/vid", response_class=HTMLResponse)
async def show_video(request: Request):
    return templates.TemplateResponse("video.html", {"request":request})


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await manager.connect(websocket, is_streamer=True)
    try:
        while True:
            data = await websocket.receive_bytes()
            if len(data) == 0:
                logger.warning("Received empty data packet")
                continue

            logger.debug(f"Received {len(data)} bytes from streamer")
            await manager.broadcast(data)

    except WebSocketDisconnect as e:
        logger.info(f"Streamer disconnected: {e}")
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Streamer error: {e}")
        manager.disconnect(websocket)


@app.websocket("/ws/watch")
async def websocket_watch(websocket: WebSocket):
    await manager.connect(websocket, is_streamer=False)
    try:
        # Отправим информацию о состоянии стрима
        await websocket.send_json({
            "type":"stream_status",
            "is_active":manager.is_stream_active(),
            "last_data_time":manager.last_data_time
        })

        # Просто ждем закрытия соединения
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        logger.info("Viewer disconnected normally")
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
    if manager.streamer_connection:
        await manager.streamer_connection.close(code=1001, reason="Server shutdown")
    for connection in manager.active_connections.copy():
        await connection.close(code=1001, reason="Server shutdown")