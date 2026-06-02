from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint, Float
from datetime import datetime
from db import Base


class CommissionSlip(Base):
    __tablename__ = "commission_slips"
    __table_args__ = (UniqueConstraint('counsellor_id', 'month', 'year', name='uix_counsellor_month_year'),)

    commission_id = Column(String, primary_key=True, index=True)
    counsellor_id = Column(String, ForeignKey("counsellors.counsellor_id"), nullable=False, index=True)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    admitted_students = Column(Integer, nullable=True, default=0)
    per_student_commission = Column(Float, nullable=True, default=0)
    total_amount = Column(Float, nullable=True, default=0)
    payment_mode = Column(String, default='NEFT')
    transaction_id = Column(String, nullable=True)
    status = Column(String, default='Paid')
    file_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<CommissionSlip(commission_id={self.commission_id}, counsellor_id={self.counsellor_id}, month={self.month}, year={self.year}, amount={self.total_amount})>"

class CommissionLedger(Base):
    __tablename__ = "commission_ledger"

    id = Column(String, primary_key=True, index=True)
    counsellor_id = Column(String, ForeignKey("counsellors.counsellor_id"), nullable=False, index=True)
    student_id = Column(String, ForeignKey("students.student_id"), nullable=False, index=True)
    payment_id = Column(String, ForeignKey("fees.fee_id"), nullable=False, index=True)
    commission_rate = Column(Float, nullable=False, default=0)
    commission_amount = Column(Float, nullable=False, default=0)
    status = Column(String, default='Pending') # Pending, Approved, Paid
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<CommissionLedger(id={self.id}, amount={self.commission_amount}, status={self.status})>"

class Payout(Base):
    __tablename__ = "payouts"

    id = Column(String, primary_key=True, index=True)
    payout_no = Column(String, unique=True, index=True, nullable=False)
    counsellor_id = Column(String, ForeignKey("counsellors.counsellor_id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    payment_method = Column(String, nullable=False)
    reference_no = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    status = Column(String, default='Paid')
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Payout(payout_no={self.payout_no}, amount={self.amount})>"

