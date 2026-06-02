from sqlalchemy import Column, String, DateTime, ForeignKey, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from db import Base

class StudentAdmission(Base):
    __tablename__ = "student_admissions"

    admission_id = Column(String, primary_key=True, index=True)
    student_id = Column(String, ForeignKey("students.student_id"), nullable=False, index=True)
    counsellor_id = Column(String, ForeignKey("counsellors.counsellor_id"), nullable=False, index=True)
    course_id = Column(String, ForeignKey("courses.course_id"), nullable=False, index=True)
    admission_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    student = relationship("Student", backref="admissions")
    counsellor = relationship("Counsellor", backref="admissions")
    course = relationship("Course", backref="admissions")

    def __repr__(self):
        return f"<StudentAdmission(admission_id={self.admission_id}, student_id={self.student_id})>"
