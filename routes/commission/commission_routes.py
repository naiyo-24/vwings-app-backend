from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional, List
from pathlib import Path
from datetime import datetime
import os
from fastapi.responses import FileResponse

from db import get_db
from models.commission.commission_models import CommissionSlip
from models.auth.counsellor_models import Counsellor
from services.commission_id_generator import generate_commission_id
from pydantic import BaseModel

router = APIRouter(prefix="/api/commissions", tags=["Commissions"])


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
        file_path=saved_path,
        created_at=now,
        updated_at=now,
    )
    db.add(commission)
    db.commit()
    db.refresh(commission)
    return commission


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
