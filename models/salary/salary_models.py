from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Float
from datetime import datetime
from db import Base


class Salary(Base):
    __tablename__ = "salaries"

    salary_id = Column(String, primary_key=True, index=True)
    teacher_id = Column(String, ForeignKey("teachers.teacher_id"), nullable=False, index=True)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    fixed_salary = Column(Float, default=0.0)
    commission_per_student = Column(Float, default=0.0)
    referrals_admitted = Column(Integer, default=0)
    total_salary = Column(Float, default=0.0)
    payment_mode = Column(String, default="NEFT")
    transaction_id = Column(String, nullable=True)
    status = Column(String, default="Paid")
    file_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Salary(salary_id={self.salary_id}, teacher_id={self.teacher_id}, month={self.month}, year={self.year})>"
