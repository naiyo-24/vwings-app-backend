from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Enum as SQLEnum
from datetime import datetime
from db import Base
import enum

class PaymentType(str, enum.Enum):
    FULL = "full"
    INSTALLMENT = "installment"

class Fee(Base):
    __tablename__ = "fees"

    fee_id = Column(String, primary_key=True, index=True)
    student_id = Column(String, ForeignKey("students.student_id"), nullable=False, index=True)
    installment_no = Column(Integer, nullable=False)
    file_path = Column(String, nullable=True)
    payment_type = Column(String, nullable=True) # 'full' or 'installment'
    payment_mode = Column(String, default="online") # 'online', 'cash', 'cheque', or 'demand_draft'
    amount = Column(Integer, nullable=True)
    payment_status = Column(String, default="pending")
    razorpay_order_id = Column(String, nullable=True)
    razorpay_payment_id = Column(String, nullable=True)
    cheque_no = Column(String, nullable=True)
    dd_no = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Fee(fee_id={self.fee_id}, student_id={self.student_id}, amount={self.amount})>"

class StudentFeeProfile(Base):
    __tablename__ = "student_fee_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(String, ForeignKey("students.student_id"), unique=True, nullable=False, index=True)
    total_fee = Column(Float, nullable=False, default=0.0)
    payment_plan = Column(String, nullable=False, default="full") # "full" or "installment"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
