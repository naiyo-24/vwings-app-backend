from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from datetime import datetime
from db import Base

class Announcement(Base):
	__tablename__ = "announcements"

	announcement_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
	headline = Column(String(255), nullable=False)
	description = Column(Text, nullable=False)
	# role: which audience this announcement is for (student, counsellor, teacher)
	role = Column(String(50), nullable=False, default="student")
	target_id = Column(String(50), nullable=True, default=None)
	active_status = Column(Boolean, default=True)
	created_at = Column(DateTime, default=datetime.utcnow)
	updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
