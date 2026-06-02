from sqlalchemy.orm import Session
from datetime import datetime
from models.fees.fees_models import Fee
from models.admission.student_admission_models import StudentAdmission
from models.commission.commission_models import CommissionLedger
from models.auth.counsellor_models import Counsellor
from models.courses.course_models import Course
import uuid

def process_commission(fee: Fee, db: Session):
    # Only process if payment is completed
    if fee.payment_status != "completed":
        return

    # Check if a commission ledger entry already exists for this payment
    existing = db.query(CommissionLedger).filter_by(payment_id=fee.fee_id).first()
    if existing:
        return

    # Find if the student was admitted by a counsellor
    admission = db.query(StudentAdmission).filter_by(student_id=fee.student_id).first()
    if not admission:
        return
        
    counsellor = db.query(Counsellor).filter_by(counsellor_id=admission.counsellor_id).first()
    if not counsellor:
        return
        
    # Commission Rule configuration
    # Priority: Counsellor Rule ↓ Course Rule ↓ Default Institute Rule
    # Let's determine the percentage or fixed amount
    
    commission_type = counsellor.commission_type or "default"
    commission_value = counsellor.commission_value or 0.0
    
    amount_paid = fee.amount or 0
    calculated_commission = 0.0
    rate_used = 0.0
    
    if commission_type == "percentage":
        calculated_commission = (amount_paid * commission_value) / 100.0
        rate_used = commission_value
    elif commission_type == "fixed":
        # Fixed commission: wait, is it prorated or given fully on first payment?
        # User said:
        # Example: Course Fee = 50k, Commission = 10%. Payment 1: 20k -> 2k.
        # If it's fixed, e.g., 2000 per admission. Let's say we give a percentage of the payment based on the total fee.
        # Or maybe if it's fixed, we just give a proportional amount?
        # "Commission should only be generated when payment is received."
        # If fixed is 2000, and they pay 20k out of 50k (40%), they should get 800.
        
        # We need total fee
        total_fee = 0
        from models.fees.fees_models import StudentFeeProfile
        profile = db.query(StudentFeeProfile).filter_by(student_id=fee.student_id).first()
        if profile and profile.total_fee > 0:
            total_fee = profile.total_fee
        else:
            course = db.query(Course).filter_by(course_id=admission.course_id).first()
            if course and course.general_data:
                total_fee = float(course.general_data.get("course_fees", 0.0))
                
        if total_fee > 0:
            ratio = amount_paid / total_fee
            calculated_commission = commission_value * ratio
        else:
            # Fallback if no total fee is found, give the whole fixed amount on first payment
            calculated_commission = commission_value
            
        rate_used = commission_value # We can store the fixed value here
    else:
        # Default rule, maybe 10%
        calculated_commission = (amount_paid * 10.0) / 100.0
        rate_used = 10.0
        
    if calculated_commission > 0:
        ledger = CommissionLedger(
            id=str(uuid.uuid4()),
            counsellor_id=counsellor.counsellor_id,
            student_id=fee.student_id,
            payment_id=fee.fee_id,
            commission_rate=rate_used,
            commission_amount=calculated_commission,
            status="Pending",
            created_at=datetime.utcnow()
        )
        db.add(ledger)
        db.commit()
