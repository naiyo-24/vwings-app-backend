from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from db import get_db, SessionLocal
from models.notification.notification_models import Notification
from datetime import datetime
import asyncio

router = APIRouter(tags=["Notifications"])

# Store active websocket connections
# structure: { "admin": { "admin_id_1": [ws1, ws2] }, "student": {...} }
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, List[WebSocket]]] = {
            "admin": {},
            "student": {},
            "teacher": {},
            "counsellor": {}
        }

    async def connect(self, websocket: WebSocket, role: str, user_id: str):
        await websocket.accept()
        if role not in self.active_connections:
            self.active_connections[role] = {}
        if user_id not in self.active_connections[role]:
            self.active_connections[role][user_id] = []
        self.active_connections[role][user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, role: str, user_id: str):
        if role in self.active_connections and user_id in self.active_connections[role]:
            if websocket in self.active_connections[role][user_id]:
                self.active_connections[role][user_id].remove(websocket)

    async def send_personal_message(self, message: dict, role: str, user_id: str):
        if role in self.active_connections and user_id in self.active_connections[role]:
            for connection in self.active_connections[role][user_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass
                
    async def broadcast_to_role(self, message: dict, role: str):
        if role in self.active_connections:
            for user_id, connections in self.active_connections[role].items():
                for connection in connections:
                    try:
                        await connection.send_json(message)
                    except:
                        pass

manager = ConnectionManager()

@router.websocket("/ws/{role}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, role: str, user_id: str):
    await manager.connect(websocket, role, user_id)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, role, user_id)

@router.get("/api/notifications/get/{role}/{user_id}")
def get_notifications(role: str, user_id: str, db: Session = Depends(get_db)):
    notifs = db.query(Notification).filter(
        Notification.recipient_role == role,
        (Notification.recipient_id == user_id) | (Notification.recipient_id == None)
    ).order_by(Notification.created_at.desc()).all()
    return notifs

@router.put("/api/notifications/mark-read/{notification_id}")
def mark_read(notification_id: int, db: Session = Depends(get_db)):
    notif = db.query(Notification).filter(Notification.notification_id == notification_id).first()
    if notif:
        notif.is_read = True
        db.commit()
    return {"status": "success"}

@router.put("/api/notifications/mark-all-read/{role}/{user_id}")
def mark_all_read(role: str, user_id: str, db: Session = Depends(get_db)):
    db.query(Notification).filter(
        Notification.recipient_role == role,
        (Notification.recipient_id == user_id) | (Notification.recipient_id == None),
        Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"status": "success"}

async def _create_notification_async(title: str, message: str, role: str, user_id: Optional[str] = None):
    db = SessionLocal()
    try:
        new_notif = Notification(
            recipient_role=role,
            recipient_id=user_id,
            title=title,
            message=message
        )
        db.add(new_notif)
        db.commit()
        db.refresh(new_notif)
        
        ws_msg = {
            "notification_id": new_notif.notification_id,
            "title": new_notif.title,
            "message": new_notif.message,
            "is_read": False,
            "created_at": new_notif.created_at.isoformat()
        }
        
        if user_id:
            await manager.send_personal_message(ws_msg, role, user_id)
        else:
            await manager.broadcast_to_role(ws_msg, role)
    finally:
        db.close()

def create_notification(title: str, message: str, role: str, user_id: Optional[str] = None):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_create_notification_async(title, message, role, user_id))
    except RuntimeError:
        asyncio.run(_create_notification_async(title, message, role, user_id))
