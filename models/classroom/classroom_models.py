from sqlalchemy import Column, String, DateTime, JSON, ForeignKey
from sqlalchemy.ext.mutable import MutableList
from datetime import datetime
from db import Base


class Classroom(Base):
	__tablename__ = "classrooms"

	class_id = Column(String, primary_key=True, index=True)
	class_name = Column(String, nullable=False)
	class_description = Column(String, nullable=True)
	class_photo = Column(String, nullable=True)  # Path to photo file
	meet_link = Column(String, nullable=True)
	class_date = Column(String, nullable=True)
	class_time = Column(String, nullable=True)
	# List of teacher ids (stored as JSON array). Use application-level checks to enforce referential integrity.
	teacher_ids = Column(MutableList.as_mutable(JSON), nullable=True)
	# Admin who created/owns the class (FK to admins.id)
	admin_id = Column(String, ForeignKey("admins.id"), nullable=True)
	# List of student ids (stored as JSON array)
	student_ids = Column(MutableList.as_mutable(JSON), nullable=True)
	created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
	updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

