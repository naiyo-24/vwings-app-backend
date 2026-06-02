from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List
from db import get_db, SessionLocal
from models.classroom.class_chat_models import ClassChatMessage
from models.classroom.classroom_models import Classroom
from datetime import datetime
import json
import threading
import asyncio
from models.auth.student_models import Student
from models.auth.teacher_models import Teacher
from models.auth.admin_models import Admin
from fastapi import UploadFile, File, Form
import os
import shutil
from uuid import uuid4

router = APIRouter(prefix="/api/classrooms", tags=["ClassroomChat"])

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        # map class_id -> set of websockets
        self.active: dict[str, set[WebSocket]] = {}

    async def connect(self, class_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active.setdefault(class_id, set()).add(websocket)

    def disconnect(self, class_id: str, websocket: WebSocket):
        conns = self.active.get(class_id)
        if conns and websocket in conns:
            conns.remove(websocket)

    async def broadcast(self, class_id: str, message: dict):
        conns = list(self.active.get(class_id, []))
        for ws in conns:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                # ignore individual send errors
                pass


manager = ConnectionManager()

# helper to check if user is admin or teacher for the class
def is_admin_or_teacher_for_class(db: Session, class_id: str, user_id: str) -> bool:
    cls = db.query(Classroom).filter(Classroom.class_id == class_id).first()
    if not cls:
        return False
    if cls.admin_id == user_id:
        return True
    if cls.teacher_ids and user_id in (cls.teacher_ids or []):
        return True
    return False


def _resolve_sender_name(db: Session, sender_role: str, sender_id: str):
    try:
        if sender_role == 'teacher':
            t = db.query(Teacher).filter(Teacher.teacher_id == sender_id).first()
            return t.full_name if t else None
        if sender_role == 'student':
            s = db.query(Student).filter(Student.student_id == sender_id).first()
            return s.full_name if s else None
        if sender_role == 'admin':
            a = db.query(Admin).filter(Admin.id == sender_id).first()
            return getattr(a, 'email', None) if a else None
    except Exception:
        return None
    return None

# get all messages for a class
@router.get("/get-by/{class_id}/messages", response_model=List[dict])
def get_messages(class_id: str, db: Session = Depends(get_db)):
    msgs = db.query(ClassChatMessage).filter(ClassChatMessage.class_id == class_id).order_by(ClassChatMessage.created_at.asc()).all()
    return [
        {
            "message_id": m.message_id,
            "class_id": m.class_id,
            "sender_id": m.sender_id,
            "sender_role": m.sender_role,
            "sender_name": _resolve_sender_name(db, m.sender_role, m.sender_id),
            "content": m.content,
            "attachment_url": m.attachment_url,
            "attachment_type": m.attachment_type,
            "created_at": m.created_at,
        }
        for m in msgs
    ]

# POST a new message to class chat on the basis of sender role- only class admins (teachers/admin) can post messages
@router.post("/post-to/{class_id}/messages")
def post_message(class_id: str, payload: dict, db: Session = Depends(get_db)):
    # payload must contain sender_id and sender_role and content
    sender_id = payload.get("sender_id")
    sender_role = payload.get("sender_role")
    content = payload.get("content")
    if not sender_id or not sender_role or not content:
        raise HTTPException(status_code=400, detail="sender_id, sender_role and content required")
    if not is_admin_or_teacher_for_class(db, class_id, sender_id):
        raise HTTPException(status_code=403, detail="Only class admins (teachers/admin) can post messages")
    attachment_url = payload.get("attachment_url")
    attachment_type = payload.get("attachment_type")
    
    msg = ClassChatMessage(
        class_id=class_id,
        sender_id=sender_id,
        sender_role=sender_role,
        content=content,
        attachment_url=attachment_url,
        attachment_type=attachment_type,
        created_at=datetime.utcnow(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    # resolve sender name for broadcast
    sender_name = _resolve_sender_name(db, msg.sender_role, msg.sender_id)
    # broadcast to websocket clients in a background thread to avoid "no running event loop"
    def _broadcast():
        asyncio.run(manager.broadcast(class_id, {
            "message_id": msg.message_id,
            "class_id": msg.class_id,
            "sender_id": msg.sender_id,
            "sender_role": msg.sender_role,
            "sender_name": sender_name,
            "content": msg.content,
            "attachment_url": msg.attachment_url,
            "attachment_type": msg.attachment_type,
            "created_at": msg.created_at.isoformat(),
        }))

    threading.Thread(target=_broadcast, daemon=True).start()
    return {"message_id": msg.message_id}

# WebSocket endpoint for real-time chat
@router.websocket("/ws/{class_id}/chat")
async def websocket_chat(websocket: WebSocket, class_id: str, user_id: str = None, role: str = None):
    # Query parameters: ?user_id=...&role=...
    await manager.connect(class_id, websocket)
    db = SessionLocal()
    try:
        while True:
            try:
                data = await websocket.receive_text()
            except WebSocketDisconnect:
                manager.disconnect(class_id, websocket)
                break
            except RuntimeError:
                # websocket not connected or accept not completed on client side
                manager.disconnect(class_id, websocket)
                break
            except Exception:
                # other receive errors: stop handling this connection
                manager.disconnect(class_id, websocket)
                break
            # expect JSON messages from client
            try:
                payload = json.loads(data)
            except Exception:
                await websocket.send_text(json.dumps({"error": "invalid json"}))
                continue

            # if client intends to send a chat message, payload should contain 'content' and 'sender_id'
            content = payload.get("content")
            sender_id = payload.get("sender_id") or user_id
            sender_role = payload.get("sender_role") or role

            if not content or not sender_id or not sender_role:
                # ignore malformed messages
                await websocket.send_text(json.dumps({"error": "content, sender_id and sender_role required"}))
                continue

            # only admins (class admin or teacher) can send; others can only receive
            # Allow sending by:
            # - admins (class admin)
            # - teachers listed in classroom.teacher_ids
            # - students only if they are members of the classroom
            cls = db.query(Classroom).filter(Classroom.class_id == class_id).first()
            if not cls:
                await websocket.send_text(json.dumps({"error": "class not found"}))
                continue
            if sender_role == "student":
                # Allow any student to participate in real-time chat regardless of membership
                pass
            else:
                if not is_admin_or_teacher_for_class(db, class_id, sender_id):
                    await websocket.send_text(json.dumps({"error": "not authorized to send messages"}))
                    continue

            attachment_url = payload.get("attachment_url")
            attachment_type = payload.get("attachment_type")

            # persist message
            msg = ClassChatMessage(
                class_id=class_id,
                sender_id=sender_id,
                sender_role=sender_role,
                content=content,
                attachment_url=attachment_url,
                attachment_type=attachment_type,
                created_at=datetime.utcnow(),
            )
            db.add(msg)
            db.commit()
            db.refresh(msg)

            # broadcast
            await manager.broadcast(class_id, {
                "message_id": msg.message_id,
                "class_id": msg.class_id,
                "sender_id": msg.sender_id,
                "sender_role": msg.sender_role,
                "sender_name": _resolve_sender_name(db, msg.sender_role, msg.sender_id),
                "content": msg.content,
                "attachment_url": msg.attachment_url,
                "attachment_type": msg.attachment_type,
                "created_at": msg.created_at.isoformat(),
            })

    except WebSocketDisconnect:
        manager.disconnect(class_id, websocket)
    finally:
        db.close()


@router.delete("/delete/{class_id}/messages/{message_id}")
def delete_message(class_id: str, message_id: str, requester_id: str, db: Session = Depends(get_db)):
    """Delete a chat message. Only class admins (teachers/admin) may delete messages."""
    msg = db.query(ClassChatMessage).filter(ClassChatMessage.message_id == message_id,
                                           ClassChatMessage.class_id == class_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    # only class admin/teachers can delete
    if not is_admin_or_teacher_for_class(db, class_id, requester_id):
        raise HTTPException(status_code=403, detail="Not authorized to delete message")

    db.delete(msg)
    db.commit()
    # broadcast deletion event so clients can remove message locally
    def _broadcast_del():
        asyncio.run(manager.broadcast(class_id, {"deleted_message_id": message_id}))

    threading.Thread(target=_broadcast_del, daemon=True).start()
    return {"message": "deleted", "message_id": message_id}


# Student-specific endpoints
@router.get("/student/{class_id}/messages", response_model=List[dict])
def student_get_messages(class_id: str, student_id: str, db: Session = Depends(get_db)):
    """Return chat messages for a class — student must be a member to view."""
    cls = db.query(Classroom).filter(Classroom.class_id == class_id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Classroom not found")
    if not cls.student_ids or student_id not in (cls.student_ids or []):
        raise HTTPException(status_code=403, detail="Student not a member of this classroom")
    msgs = db.query(ClassChatMessage).filter(ClassChatMessage.class_id == class_id).order_by(ClassChatMessage.created_at.asc()).all()
    return [
        {
            "message_id": m.message_id,
            "class_id": m.class_id,
            "sender_id": m.sender_id,
            "sender_role": m.sender_role,
            "sender_name": _resolve_sender_name(db, m.sender_role, m.sender_id),
            "content": m.content,
            "attachment_url": m.attachment_url,
            "attachment_type": m.attachment_type,
            "created_at": m.created_at,
        }
        for m in msgs
    ]


@router.post("/student/{class_id}/messages")
def student_post_message(class_id: str, payload: dict, student_id: str, db: Session = Depends(get_db)):
    """Student posts a message — students may participate in real-time chat."""
    cls = db.query(Classroom).filter(Classroom.class_id == class_id).first()
    if not cls:
        raise HTTPException(status_code=404, detail="Classroom not found")

    content = payload.get("content")
    if not content:
        raise HTTPException(status_code=400, detail="content required")
    attachment_url = payload.get("attachment_url")
    attachment_type = payload.get("attachment_type")

    msg = ClassChatMessage(
        class_id=class_id,
        sender_id=student_id,
        sender_role="student",
        content=content,
        attachment_url=attachment_url,
        attachment_type=attachment_type,
        created_at=datetime.utcnow(),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # broadcast in background
    def _broadcast_student():
        asyncio.run(manager.broadcast(class_id, {
            "message_id": msg.message_id,
            "class_id": msg.class_id,
            "sender_id": msg.sender_id,
            "sender_role": msg.sender_role,
            "sender_name": _resolve_sender_name(db, msg.sender_role, msg.sender_id),
            "content": msg.content,
            "attachment_url": msg.attachment_url,
            "attachment_type": msg.attachment_type,
            "created_at": msg.created_at.isoformat(),
        }))

    threading.Thread(target=_broadcast_student, daemon=True).start()
    return {"message_id": msg.message_id}

@router.post("/upload-attachment")
async def upload_attachment(file: UploadFile = File(...)):
    UPLOAD_DIR = "uploads/chat_attachments"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    file_id = str(uuid4().hex[:8])
    ext = os.path.splitext(file.filename)[1]
    filename = f"{file_id}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    attachment_type = "image" if ext.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp'] else "pdf" if ext.lower() == '.pdf' else "file"
    
    return {
        "url": file_path.replace("\\", "/"),
        "type": attachment_type
    }

