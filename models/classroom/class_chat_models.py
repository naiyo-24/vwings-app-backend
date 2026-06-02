from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from datetime import datetime
from uuid import uuid4
from db import Base


def generate_message_id() -> str:
    return f"MSG-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:-3]}-{uuid4().hex[:8]}"


class ClassChatMessage(Base):
    __tablename__ = "class_chat_messages"

    message_id = Column(String, primary_key=True, index=True, default=generate_message_id)
    class_id = Column(String, ForeignKey("classrooms.class_id"), nullable=False, index=True)
    sender_id = Column(String, nullable=False)
    sender_role = Column(String, nullable=False)  # e.g., 'admin', 'teacher', 'student'
    content = Column(Text, nullable=False)
    attachment_url = Column(String, nullable=True)
    attachment_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<ClassChatMessage(message_id={self.message_id}, class_id={self.class_id})>"
