from sqlalchemy import Column, String, Text, DateTime, JSON, Float
from datetime import datetime
from db import Base

class Counsellor(Base):
	__tablename__ = "counsellors"

	counsellor_id = Column(String, primary_key=True, index=True)
	full_name = Column(String, nullable=False)
	phone_no = Column(String, nullable=False, unique=True, index=True)
	alternative_phone_no = Column(String, nullable=True)
	email = Column(String, nullable=False, unique=True, index=True)
	address = Column(Text, nullable=True)
	qualification = Column(String, nullable=True)
	experience = Column(String, nullable=True)
	bank_account_no = Column(String, nullable=True)
	bank_account_name = Column(String, nullable=True)
	branch_name = Column(String, nullable=True)
	ifsc_code = Column(String, nullable=True)
	upi_id = Column(String, nullable=True)
	# per_courses_commission stores a mapping of course_id -> commission_percentage (e.g. {"COURSE4220": 10.5})
	per_courses_commission = Column(JSON, nullable=True)
	commission_per_student = Column(Float, default=0.0)
	commission_type = Column(String, nullable=True, default="default") # 'fixed', 'percentage', 'default'
	commission_value = Column(Float, nullable=True, default=0.0)
	status = Column(String, default="active")
	profile_photo = Column(String, nullable=True)
	password = Column(String, nullable=False)
	created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
	updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

	def __repr__(self):
		return f"<Counsellor(counsellor_id={self.counsellor_id}, full_name={self.full_name})>"
