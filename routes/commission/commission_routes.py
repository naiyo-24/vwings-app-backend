from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional, List
from pathlib import Path
from datetime import datetime
import os
import uuid
from fastapi.responses import FileResponse

from db import get_db
from models.commission.commission_models import CommissionSlip, CommissionLedger, Payout
from models.auth.counsellor_models import Counsellor
from models.fees.fees_models import Fee
from services.commission_id_generator import generate_commission_id
from pydantic import BaseModel
from services.commission_pdf_generator import generate_commission_slip_pdf

router = APIRouter(prefix="/api/commissions", tags=["Commissions"])

class CommissionCalculationRequest(BaseModel):
    counsellor_id: str
    month: int
    year: int
    commission_per_student: float
    admitted_students: int
    transaction_id: str


class CommissionBase(BaseModel):
    counsellor_id: str
    month: int
    year: int
    file_path: Optional[str] = None


class CommissionCreate(CommissionBase):
    pass


class CommissionOut(CommissionBase):
    commission_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.post("/create", response_model=CommissionOut, status_code=status.HTTP_201_CREATED)
async def create_commission(
    counsellor_id: str = Form(...),
    month: int = Form(...),
    year: int = Form(...),
    admitted_students: int = Form(0),
    per_student_commission: float = Form(0.0),
    total_amount: float = Form(0.0),
    file: Optional[UploadFile] = File(None),
    file_path: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    # validate counsellor exists
    if not db.query(Counsellor).filter_by(counsellor_id=counsellor_id).first():
        raise HTTPException(status_code=400, detail="Invalid counsellor_id")

    # avoid duplicate month-year for same counsellor
    existing = db.query(CommissionSlip).filter_by(counsellor_id=counsellor_id, month=month, year=year).first()
    if existing:
        raise HTTPException(status_code=400, detail="Commission slip already exists for this counsellor and month/year")

    now = datetime.utcnow()
    commission_id = generate_commission_id(now)

    saved_path = None
    if file:
        uploads_dir = Path("uploads/commissions") / commission_id
        uploads_dir.mkdir(parents=True, exist_ok=True)
        dest = uploads_dir / file.filename
        with dest.open("wb") as f:
            contents = await file.read()
            f.write(contents)
        saved_path = str(dest)
    elif file_path:
        saved_path = file_path

    commission = CommissionSlip(
        commission_id=commission_id,
        counsellor_id=counsellor_id,
        month=month,
        year=year,
        admitted_students=admitted_students,
        per_student_commission=per_student_commission,
        total_amount=total_amount,
        file_path=saved_path,
        created_at=now,
        updated_at=now,
    )
    db.add(commission)
    db.commit()
    db.refresh(commission)
    return commission

from fastapi import Body

@router.post("/calculate-and-pay", response_model=dict, status_code=status.HTTP_201_CREATED)
async def calculate_and_pay_commission(
    request: CommissionCalculationRequest = Body(...),
    db: Session = Depends(get_db)
):
    counsellor = db.query(Counsellor).filter_by(counsellor_id=request.counsellor_id).first()
    if not counsellor:
        raise HTTPException(status_code=404, detail="Counsellor not found")
        
    now = datetime.utcnow()
    commission_id = generate_commission_id(now)
    
    total_amount = request.admitted_students * request.commission_per_student
    
    # generate pdf
    uploads_dir = Path("uploads/commissions") / commission_id
    uploads_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{commission_id}_commission_slip.pdf"
    file_path = uploads_dir / filename
    
    commission_data = {
        'counsellor_name': counsellor.full_name,
        'counsellor_id': counsellor.counsellor_id,
        'month': request.month,
        'year': request.year,
        'commission_per_student': request.commission_per_student,
        'admitted_students': request.admitted_students,
        'total_amount': total_amount,
        'transaction_id': request.transaction_id,
        'payment_mode': 'NEFT'
    }
    
    generate_commission_slip_pdf(commission_data, str(file_path))
    
    db_commission = CommissionSlip(
        commission_id=commission_id,
        counsellor_id=request.counsellor_id,
        month=request.month,
        year=request.year,
        admitted_students=request.admitted_students,
        per_student_commission=request.commission_per_student,
        total_amount=total_amount,
        payment_mode='NEFT',
        transaction_id=request.transaction_id,
        status='Paid',
        file_path=str(file_path),
        created_at=now,
        updated_at=now,
    )
    db.add(db_commission)
    db.commit()
    db.refresh(db_commission)
    
    return {"detail": "Commission calculated and paid successfully", "commission_id": commission_id}



@router.get("/get-by/{commission_id}", response_model=CommissionOut)
def get_commission_by_id(commission_id: str, db: Session = Depends(get_db)):
    commission = db.query(CommissionSlip).filter_by(commission_id=commission_id).first()
    if not commission:
        raise HTTPException(status_code=404, detail="Commission slip not found")
    return commission


@router.get("/get-by-counsellor/{counsellor_id}", response_model=List[CommissionOut])
def get_commissions_for_counsellor(counsellor_id: str, db: Session = Depends(get_db)):
    commissions = db.query(CommissionSlip).filter_by(counsellor_id=counsellor_id).order_by(CommissionSlip.year.desc(), CommissionSlip.month.desc()).all()
    return commissions


@router.get("/get-all", response_model=List[CommissionOut])
def get_all_commissions(db: Session = Depends(get_db)):
    commissions = db.query(CommissionSlip).order_by(CommissionSlip.year.desc(), CommissionSlip.month.desc()).all()
    return commissions


# Download commission slip PDF by counsellor id, month, and year
@router.get("/download/{counsellor_id}/{month}/{year}")
def download_commission(counsellor_id: str, month: int, year: int, db: Session = Depends(get_db)):
    # Verify counsellor exists
    counsellor = db.query(Counsellor).filter_by(counsellor_id=counsellor_id).first()
    if not counsellor:
        raise HTTPException(status_code=404, detail="Counsellor not found")

    # Get the commission record
    commission = db.query(CommissionSlip).filter_by(counsellor_id=counsellor_id, month=month, year=year).first()
    if not commission:
        raise HTTPException(status_code=404, detail="Commission slip not found for this month and year")

    # Check if file exists
    if not os.path.exists(commission.file_path):
        raise HTTPException(status_code=404, detail="Commission slip file not found")

    # Return the file
    return FileResponse(path=commission.file_path, filename=f"commission_{counsellor_id}_{month}_{year}.pdf", media_type='application/pdf')


@router.put("/put-by/{commission_id}", response_model=CommissionOut)
async def update_commission(
    commission_id: str,
    file: Optional[UploadFile] = File(None),
    file_path: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    commission = db.query(CommissionSlip).filter_by(commission_id=commission_id).first()
    if not commission:
        raise HTTPException(status_code=404, detail="Commission slip not found")

    if file:
        uploads_dir = Path("uploads/commissions") / commission_id
        uploads_dir.mkdir(parents=True, exist_ok=True)
        dest = uploads_dir / file.filename
        with dest.open("wb") as f:
            contents = await file.read()
            f.write(contents)
        commission.file_path = str(dest)
    elif file_path:
        commission.file_path = file_path

    commission.updated_at = datetime.utcnow()
    db.add(commission)
    db.commit()
    db.refresh(commission)
    return commission


@router.delete("/delete-by/{commission_id}", response_model=dict)
def delete_commission(commission_id: str, db: Session = Depends(get_db)):
    commission = db.query(CommissionSlip).filter_by(commission_id=commission_id).first()
    if not commission:
        raise HTTPException(status_code=404, detail="Commission slip not found")
    # optional: remove file from disk if present
    if commission.file_path and os.path.exists(commission.file_path):
        try:
            os.remove(commission.file_path)
        except Exception:
            pass
    db.delete(commission)
    db.commit()
    return {"detail": "deleted"}


@router.delete("/bulk-delete", response_model=dict)
def bulk_delete_commissions(ids: List[str] = Form(...), db: Session = Depends(get_db)):
    deleted = 0
    for cid in ids:
        commission = db.query(CommissionSlip).filter_by(commission_id=cid).first()
        if commission:
            if commission.file_path and os.path.exists(commission.file_path):
                try:
                    os.remove(commission.file_path)
                except Exception:
                    pass
            db.delete(commission)
            deleted += 1
    db.commit()
    return {"deleted": deleted}


from sqlalchemy import extract
from models.admission.admission_enquiry_models import AdmissionEnquiry

@router.get("/calculate/{counsellor_id}/{month}/{year}")
def calculate_commission(counsellor_id: str, month: int, year: int, db: Session = Depends(get_db)):
    counsellor = db.query(Counsellor).filter_by(counsellor_id=counsellor_id).first()
    if not counsellor:
        raise HTTPException(status_code=404, detail="Counsellor not found")
    
    # count admitted students in this month and year
    count = db.query(AdmissionEnquiry).filter(
        AdmissionEnquiry.counsellor_id == counsellor_id,
        AdmissionEnquiry.status == "converted",
        extract('month', AdmissionEnquiry.updated_at) == month,
        extract('year', AdmissionEnquiry.updated_at) == year
    ).count()
    
    per_student = counsellor.commission_per_student or 0.0
    total = count * per_student
    
    return {
        "counsellor_id": counsellor.counsellor_id,
        "admitted_students": count,
        "commission_per_student": per_student,
        "total_commission": total
    }

class LedgerStatusUpdate(BaseModel):
    status: str

@router.get("/ledger")
def get_commission_ledger(counsellor_id: Optional[str] = None, status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(CommissionLedger)
    if counsellor_id:
        query = query.filter(CommissionLedger.counsellor_id == counsellor_id)
    if status:
        query = query.filter(CommissionLedger.status == status)
    return query.order_by(CommissionLedger.created_at.desc()).all()

@router.put("/ledger/{ledger_id}/status")
def update_ledger_status(ledger_id: str, request: LedgerStatusUpdate, db: Session = Depends(get_db)):
    ledger = db.query(CommissionLedger).filter_by(id=ledger_id).first()
    if not ledger:
        raise HTTPException(status_code=404, detail="Ledger not found")
    ledger.status = request.status
    db.commit()
    return {"detail": "Status updated", "ledger_id": ledger_id, "status": request.status}

class GeneratePayoutRequest(BaseModel):
    counsellor_id: str
    payment_method: str
    reference_no: Optional[str] = None

@router.post("/payouts/generate")
def generate_payout(request: GeneratePayoutRequest, db: Session = Depends(get_db)):
    try:
        counsellor = db.query(Counsellor).filter_by(counsellor_id=request.counsellor_id).first()
        if not counsellor:
            raise HTTPException(status_code=404, detail="Counsellor not found")
            
        pending_ledgers = db.query(CommissionLedger).filter(
            CommissionLedger.counsellor_id == request.counsellor_id,
            CommissionLedger.status.in_(["Approved", "Pending"])
        ).all()
        if not pending_ledgers:
            raise HTTPException(status_code=400, detail="No pending or approved commissions to payout")
            
        total_amount = sum(l.commission_amount for l in pending_ledgers)
        
        now = datetime.utcnow()
        payout_id = str(uuid.uuid4())
        payout_no = f"PAYOUT-{now.strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        
        from services.commission_pdf_generator import generate_payout_slip_pdf
        uploads_dir = Path("uploads/payouts") / payout_id
        uploads_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{payout_no}_slip.pdf"
        file_path = uploads_dir / filename
        
        payout_data = {
            'counsellor_name': counsellor.full_name,
            'counsellor_id': counsellor.counsellor_id,
            'payout_no': payout_no,
            'payment_method': request.payment_method,
            'reference_no': request.reference_no,
            'date': now.strftime("%d-%b-%Y"),
            'amount': total_amount
        }
        
        generate_payout_slip_pdf(payout_data, str(file_path))
        
        payout = Payout(
            id=payout_id,
            payout_no=payout_no,
            counsellor_id=request.counsellor_id,
            amount=total_amount,
            payment_method=request.payment_method,
            reference_no=request.reference_no,
            file_path=str(file_path).replace("\\", "/"),
            status="Paid",
            created_at=now
        )
        db.add(payout)
        
        # Update ledger statuses
        for l in pending_ledgers:
            l.status = "Paid"
            
        db.commit()
        
        return {"detail": "Payout generated", "payout_no": payout_no, "amount": total_amount}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        raise HTTPException(status_code=500, detail=str(error_msg))

@router.get("/payouts")
def get_payouts(counsellor_id: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Payout)
    if counsellor_id:
        query = query.filter(Payout.counsellor_id == counsellor_id)
    return query.order_by(Payout.created_at.desc()).all()

@router.get("/payouts/download/{payout_id}")
def download_payout_slip(payout_id: str, db: Session = Depends(get_db)):
    payout = db.query(Payout).filter_by(id=payout_id).first()
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
        
    if not payout.file_path or not os.path.exists(payout.file_path):
        raise HTTPException(status_code=404, detail="Payout slip file not found")
        
    return FileResponse(path=payout.file_path, filename=f"payout_{payout.payout_no}.pdf", media_type='application/pdf')

@router.get("/dashboard/{counsellor_id}")
def get_counsellor_dashboard(counsellor_id: str, db: Session = Depends(get_db)):
    counsellor = db.query(Counsellor).filter_by(counsellor_id=counsellor_id).first()
    if not counsellor:
        raise HTTPException(status_code=404, detail="Counsellor not found")
        
    total_students_referred = db.query(AdmissionEnquiry).filter_by(counsellor_id=counsellor_id).count()
    from models.admission.student_admission_models import StudentAdmission
    total_admissions = db.query(StudentAdmission).filter_by(counsellor_id=counsellor_id).count()
    
    ledgers = db.query(CommissionLedger).filter_by(counsellor_id=counsellor_id).all()
    total_commission_earned = sum(l.commission_amount for l in ledgers)
    total_paid = sum(l.commission_amount for l in ledgers if l.status == "Paid")
    pending_amount = sum(l.commission_amount for l in ledgers if l.status in ["Pending", "Approved"])
    
    return {
        "total_students_referred": total_students_referred,
        "total_admissions": total_admissions,
        "total_commission_earned": total_commission_earned,
        "total_paid": total_paid,
        "pending_amount": pending_amount
    }

@router.get("/reports/performance")
def get_performance_report(db: Session = Depends(get_db)):
    counsellors = db.query(Counsellor).all()
    report = []
    
    for c in counsellors:
        total_enquiries = db.query(AdmissionEnquiry).filter_by(counsellor_id=c.counsellor_id).count()
        from models.admission.student_admission_models import StudentAdmission
        total_admissions = db.query(StudentAdmission).filter_by(counsellor_id=c.counsellor_id).count()
        
        ledgers = db.query(CommissionLedger).filter_by(counsellor_id=c.counsellor_id).all()
        commission_earned = sum(l.commission_amount for l in ledgers)
        revenue_generated = sum(f.amount for f in db.query(Fee).filter(Fee.fee_id.in_([l.payment_id for l in ledgers])))
        
        conversion_rate = (total_admissions / total_enquiries * 100) if total_enquiries > 0 else 0
        
        report.append({
            "counsellor_id": c.counsellor_id,
            "counsellor_name": c.full_name,
            "admissions": total_admissions,
            "revenue_generated": revenue_generated,
            "commission_earned": commission_earned,
            "conversion_rate": round(conversion_rate, 2)
        })
    return report

@router.get("/reports/monthly-payouts")
def get_monthly_payouts_report(month: int, year: int, db: Session = Depends(get_db)):
    from sqlalchemy import extract
    payouts = db.query(Payout).filter(
        extract('month', Payout.created_at) == month,
        extract('year', Payout.created_at) == year
    ).all()
    
    report = []
    for p in payouts:
        counsellor = db.query(Counsellor).filter_by(counsellor_id=p.counsellor_id).first()
        report.append({
            "payout_no": p.payout_no,
            "counsellor_name": counsellor.full_name if counsellor else "Unknown",
            "amount_paid": p.amount,
            "payout_date": p.created_at,
            "reference_number": p.reference_no,
            "payment_method": p.payment_method
        })
    return report


