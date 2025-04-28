from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import List, Dict
import logging
import uuid
import asyncio

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_streamers: Dict[str, WebSocket] = {}  # активные стримеры
        self.active_viewers: Dict[str, List[WebSocket]] = {}  # зрители для каждого стримера
        self.streamer_info: Dict[str, dict] = {}  # информация о стримерах

    async def connect_streamer(self, websocket: WebSocket):
        await websocket.accept()
        streamer_id = str(uuid.uuid4())
        self.active_streamers[streamer_id] = websocket
        self.active_viewers[streamer_id] = []
        self.streamer_info[streamer_id] = {"id":streamer_id}

        logger.info(f"Streamer connected: {streamer_id}")
        await self.notify_all_viewers_about_new_stream(streamer_id)
        return streamer_id

    async def connect_viewer(self, websocket: WebSocket, streamer_id: str):
        await websocket.accept()
        if streamer_id in self.active_viewers:
            self.active_viewers[streamer_id].append(websocket)
            logger.info(f"Viewer connected to stream {streamer_id}")
        else:
            await websocket.close(code=1001, reason="Stream not available")

    async def disconnect_streamer(self, streamer_id: str):
        if streamer_id in self.active_streamers:
            del self.active_streamers[streamer_id]
            # Закрываем все соединения зрителей этого стримера
            for viewer in self.active_viewers.get(streamer_id, []):
                await viewer.close(code=1001, reason="Stream ended")
            if streamer_id in self.active_viewers:
                del self.active_viewers[streamer_id]
            if streamer_id in self.streamer_info:
                del self.streamer_info[streamer_id]
            logger.info(f"Streamer disconnected: {streamer_id}")
            await self.notify_all_viewers_about_ended_stream(streamer_id)

    async def broadcast_to_viewers(self, data: bytes, streamer_id: str):
        if streamer_id in self.active_viewers:
            for viewer in self.active_viewers[streamer_id]:
                try:
                    await viewer.send_bytes(data)
                except:
                    # Удаляем отключившихся зрителей
                    self.active_viewers[streamer_id].remove(viewer)

    async def notify_all_viewers_about_new_stream(self, streamer_id: str):
        # Отправляем сообщение всем зрителям на /ws/watch о новом стриме
        for stream_id in self.active_viewers:
            for viewer in self.active_viewers[stream_id]:
                try:
                    await viewer.send_text(f"new_stream:{streamer_id}")
                except:
                    continue

    async def notify_all_viewers_about_ended_stream(self, streamer_id: str):
        # Отправляем сообщение всем зрителям на /ws/watch о завершении стрима
        for stream_id in self.active_viewers:
            for viewer in self.active_viewers[stream_id]:
                try:
                    await viewer.send_text(f"ended_stream:{streamer_id}")
                except:
                    continue


manager = ConnectionManager()


@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request":request})


@app.get("/streams", response_class=HTMLResponse)
async def show_streams(request: Request):
    return templates.TemplateResponse("streams.html", {"request":request})


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    streamer_id = await manager.connect_streamer(websocket)
    try:
        while True:
            data = await websocket.receive_bytes()
            await manager.broadcast_to_viewers(data, streamer_id)
    except WebSocketDisconnect:
        await manager.disconnect_streamer(streamer_id)
    except Exception as e:
        logger.error(f"Stream error: {e}")
        await manager.disconnect_streamer(streamer_id)


@app.websocket("/ws/watch")
async def websocket_watch(websocket: WebSocket):
    # Этот endpoint просто поддерживает соединение для получения уведомлений
    await websocket.accept()
    try:
        while True:
            # Ждем сообщения, но ничего не делаем с ними
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Watch error: {e}")


@app.websocket("/ws/stream/{streamer_id}")
async def websocket_watch_stream(websocket: WebSocket, streamer_id: str):
    await manager.connect_viewer(websocket, streamer_id)
    try:
        while True:
            # Ждем сообщения, но ничего не делаем с ними
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Watch stream error: {e}")


@app.on_event("startup")
async def startup():
    logger.info("Streaming server started")


@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down streaming server")
    # Закрываем все соединения
    for streamer_id in list(manager.active_streamers.keys()):
        await manager.disconnect_streamer(streamer_id)