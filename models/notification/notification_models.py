from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from datetime import datetime
from db import Base

class Notification(Base):
    __tablename__ = "notifications"

    notification_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    recipient_role = Column(String(50), nullable=False) # admin, student, teacher, counsellor
    recipient_id = Column(String(50), nullable=True) # if null, it's a broadcast to that role
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
