from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pathlib import Path
import os
import shutil
import json
from decimal import Decimal, InvalidOperation
from db import get_db
from models.auth.counsellor_models import Counsellor
from models.courses.course_models import Course
from services.counsellor_id_generator import generate_counsellor_id
from pydantic import BaseModel, EmailStr
from datetime import datetime
from models.admission.admission_enquiry_models import AdmissionEnquiry
from models.admission.admission_code_models import AdmissionCode
from models.commission.commission_models import CommissionSlip
from routes.notification.notification_routes import create_notification

router = APIRouter(prefix="/api/counsellors", tags=["Counsellors"])


# Helper: validate courses referenced in commission mapping and return list of course details
def validate_and_get_course_details(db: Session, commission_map: Dict[str, float]):
    if not commission_map:
        return {}
    course_ids = list(commission_map.keys())
    courses = db.query(Course).filter(Course.course_id.in_(course_ids)).all()
    found_ids = {c.course_id for c in courses}
    missing = [cid for cid in course_ids if cid not in found_ids]
    if missing:
        raise HTTPException(status_code=400, detail=f"Invalid course ids in commission map: {missing}")
    # build mapping course_id -> { commission: float, course_name: str }
    course_by_id = {c.course_id: c for c in courses}
    normalized: Dict[str, Dict[str, Any]] = {}
    for cid, raw_val in commission_map.items():
        # allow either a numeric value or a dict {"commission": <num>, "course_name": <optional>}
        payload_course_name = None
        if isinstance(raw_val, dict):
            if "commission" not in raw_val:
                raise HTTPException(status_code=400, detail=f"Missing 'commission' for course {cid}")
            raw_comm = raw_val.get("commission")
            payload_course_name = raw_val.get("course_name")
        else:
            raw_comm = raw_val

        try:
            if isinstance(raw_comm, Decimal):
                d = raw_comm
            elif isinstance(raw_comm, (int, float)):
                d = Decimal(str(raw_comm))
            elif isinstance(raw_comm, str):
                d = Decimal(raw_comm)
            else:
                raise InvalidOperation()
        except InvalidOperation:
            raise HTTPException(status_code=400, detail=f"Invalid commission value for course {cid}: {raw_comm}")

        if not d.is_finite():
            raise HTTPException(status_code=400, detail=f"Invalid commission value for course {cid}: {raw_comm}")

        course = course_by_id.get(cid)
        # prefer provided course_name in payload if present, otherwise use DB name
        course_name = payload_course_name if payload_course_name else (course.course_name if course else None)
        normalized[cid] = {"commission": float(d), "course_name": course_name}

    return normalized

# Helper: format per_courses_commission for output
def format_per_courses_commission_for_output(db: Session, commission_map: Optional[Dict]) -> Dict[str, Dict[str, Any]]:
    """Normalize stored per_courses_commission into the shape:
    { course_id: { "commission": float, "course_name": Optional[str] } }
    Handles legacy formats where values may be numeric (int/float/str) or the new dict shape.
    """
    if not commission_map:
        return {}

    course_ids = list(commission_map.keys())
    courses = db.query(Course).filter(Course.course_id.in_(course_ids)).all()
    course_by_id = {c.course_id: c for c in courses}

    out: Dict[str, Dict[str, Any]] = {}
    for cid, raw_val in commission_map.items():
        # determine commission numeric value
        if isinstance(raw_val, dict) and "commission" in raw_val:
            raw_comm = raw_val["commission"]
        else:
            raw_comm = raw_val

        try:
            # accept Decimal, int, float, numeric strings
            if isinstance(raw_comm, Decimal):
                d = raw_comm
            elif isinstance(raw_comm, (int, float)):
                d = Decimal(str(raw_comm))
            elif isinstance(raw_comm, str):
                d = Decimal(raw_comm)
            else:
                raise InvalidOperation()
        except InvalidOperation:
            raise HTTPException(status_code=500, detail=f"Invalid commission stored for course {cid}: {raw_comm}")

        if not d.is_finite():
            raise HTTPException(status_code=500, detail=f"Invalid commission stored for course {cid}: {raw_comm}")

        course = course_by_id.get(cid)
        course_name = None
        if isinstance(raw_val, dict) and raw_val.get("course_name"):
            course_name = raw_val.get("course_name")
        elif course:
            course_name = course.course_name

        out[cid] = {"commission": float(d), "course_name": course_name}

    return out


# Schemas
class CounsellorBase(BaseModel):
    full_name: str
    phone_no: str
    alternative_phone_no: Optional[str] = None
    email: EmailStr
    address: Optional[str] = None
    qualification: Optional[str] = None
    experience: Optional[str] = None
    bank_account_no: Optional[str] = None
    bank_account_name: Optional[str] = None
    branch_name: Optional[str] = None
    ifsc_code: Optional[str] = None
    upi_id: Optional[str] = None
    commission_per_student: Optional[float] = 0.0
    commission_type: Optional[str] = "default"
    commission_value: Optional[float] = 0.0
    per_courses_commission: Optional[Dict[str, Dict[str, Any]]] = None
    profile_photo: Optional[str] = None


class CounsellorCreate(CounsellorBase):
    password: str


class CounsellorUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_no: Optional[str] = None
    alternative_phone_no: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    qualification: Optional[str] = None
    experience: Optional[str] = None
    bank_account_no: Optional[str] = None
    bank_account_name: Optional[str] = None
    branch_name: Optional[str] = None
    ifsc_code: Optional[str] = None
    upi_id: Optional[str] = None
    commission_per_student: Optional[float] = None
    commission_type: Optional[str] = None
    commission_value: Optional[float] = None
    per_courses_commission: Optional[Dict[str, Dict[str, Any]]] = None
    password: Optional[str] = None
    profile_photo: Optional[str] = None


class CounsellorOut(CounsellorBase):
    counsellor_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Create Counsellor API
@router.post("/create", response_model=CounsellorOut, status_code=status.HTTP_201_CREATED)
async def create_counsellor(
    full_name: str = Form(...),
    phone_no: str = Form(...),
    email: EmailStr = Form(...),
    alternative_phone_no: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    qualification: Optional[str] = Form(None),
    experience: Optional[str] = Form(None),
    per_courses_commission: Optional[str] = Form(None),  # JSON string: {"COURSEID": percentage}
    bank_account_no: Optional[str] = Form(None),
    bank_account_name: Optional[str] = Form(None),
    branch_name: Optional[str] = Form(None),
    ifsc_code: Optional[str] = Form(None),
    upi_id: Optional[str] = Form(None),
    commission_per_student: Optional[float] = Form(0.0),
    commission_type: Optional[str] = Form("default"),
    commission_value: Optional[float] = Form(0.0),
    password: str = Form(...),
    profile_photo: Optional[UploadFile] = File(None),
    profile_photo_path: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    # uniqueness checks
    if db.query(Counsellor).filter_by(email=email).first():
        raise HTTPException(status_code=409, detail="Email already registered.")
    if db.query(Counsellor).filter_by(phone_no=phone_no).first():
        raise HTTPException(status_code=409, detail="Phone number already registered.")

    now = datetime.utcnow()
    counsellor_id = generate_counsellor_id(now)

    commission_map = None
    if per_courses_commission:
        try:
            commission_map = json.loads(per_courses_commission)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid per_courses_commission format. Provide JSON mapping of course_id to percentage.")
        commission_map = validate_and_get_course_details(db, commission_map)

    # handle profile photo save or accept existing path string
    profile_photo_path = None
    if profile_photo:
        uploads_dir = Path("uploads") / "counsellor" / counsellor_id
        uploads_dir.mkdir(parents=True, exist_ok=True)
        file_ext = os.path.splitext(profile_photo.filename)[1]
        file_name = f"profile{file_ext}"
        file_path = uploads_dir / file_name
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(profile_photo.file, buffer)
        profile_photo_path = os.path.relpath(str(file_path), os.getcwd())
    elif profile_photo_path:
        # client provided existing path string (don't copy file)
        profile_photo_path = profile_photo_path

    db_obj = Counsellor(
        counsellor_id=counsellor_id,
        full_name=full_name,
        phone_no=phone_no,
        alternative_phone_no=alternative_phone_no,
        email=email,
        address=address,
        qualification=qualification,
        experience=experience,
        per_courses_commission=commission_map,
        bank_account_no=bank_account_no,
        bank_account_name=bank_account_name,
        branch_name=branch_name,
        ifsc_code=ifsc_code,
        upi_id=upi_id,
        commission_per_student=commission_per_student,
        commission_type=commission_type,
        commission_value=commission_value,
        password=password,
        profile_photo=profile_photo_path,
        created_at=now,
        updated_at=now,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)

    per_courses_commission_out = format_per_courses_commission_for_output(db, db_obj.per_courses_commission)
    
    # Notify Counsellor and Admin
    create_notification(
        "Welcome to VWings24x7! 🎉",
        f"Hi {full_name}, your counsellor account has been successfully created.",
        "counsellor",
        counsellor_id
    )
    create_notification(
        "New Counsellor Onboarded",
        f"{full_name} has been added as an Admission Counsellor.",
        "admin"
    )

    return CounsellorOut(**{**db_obj.__dict__, "per_courses_commission": per_courses_commission_out})


# Counsellor login (email + password)
@router.post("/login", response_model=CounsellorOut)
def counsellor_login(
    email: EmailStr = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    counsellor = db.query(Counsellor).filter_by(email=email).first()
    if not counsellor or counsellor.password != password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    profile_photo_path = None
    if counsellor.profile_photo:
        try:
            profile_photo_path = os.path.relpath(str(Path(counsellor.profile_photo)), os.getcwd())
        except Exception:
            profile_photo_path = counsellor.profile_photo

    per_courses_commission_out = format_per_courses_commission_for_output(db, counsellor.per_courses_commission)
    return CounsellorOut(**{**counsellor.__dict__, "profile_photo": profile_photo_path, "per_courses_commission": per_courses_commission_out})

# GET all counsellors
@router.get("/get-all", response_model=List[CounsellorOut])
def get_all_counsellors(db: Session = Depends(get_db)):
    counsellors = db.query(Counsellor).all()
    result = []
    for c in counsellors:
        # normalize profile photo path
        profile_photo_path = None
        if c.profile_photo:
            try:
                profile_photo_path = os.path.relpath(str(Path(c.profile_photo)), os.getcwd())
            except Exception:
                profile_photo_path = c.profile_photo
        per_courses_commission_out = format_per_courses_commission_for_output(db, c.per_courses_commission)
        result.append(CounsellorOut(**{**c.__dict__, "profile_photo": profile_photo_path, "per_courses_commission": per_courses_commission_out}))
    return result

# Get counsellor by ID
@router.get("/get-by/{counsellor_id}", response_model=CounsellorOut)
def get_counsellor_by_id(counsellor_id: str, db: Session = Depends(get_db)):
    counsellor = db.query(Counsellor).filter_by(counsellor_id=counsellor_id).first()
    if not counsellor:
        raise HTTPException(status_code=404, detail="Counsellor not found")
    profile_photo_path = None
    if counsellor.profile_photo:
        try:
            profile_photo_path = os.path.relpath(str(Path(counsellor.profile_photo)), os.getcwd())
        except Exception:
            profile_photo_path = counsellor.profile_photo
        per_courses_commission_out = format_per_courses_commission_for_output(db, counsellor.per_courses_commission)
        return CounsellorOut(**{**counsellor.__dict__, "profile_photo": profile_photo_path, "per_courses_commission": per_courses_commission_out})

# Update counsellor by ID
@router.put("/put-by/{counsellor_id}", response_model=CounsellorOut)
async def update_counsellor(
    counsellor_id: str,
    full_name: Optional[str] = Form(None),
    phone_no: Optional[str] = Form(None),
    email: Optional[EmailStr] = Form(None),
    alternative_phone_no: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    qualification: Optional[str] = Form(None),
    experience: Optional[str] = Form(None),
    per_courses_commission: Optional[str] = Form(None),
    bank_account_no: Optional[str] = Form(None),
    bank_account_name: Optional[str] = Form(None),
    branch_name: Optional[str] = Form(None),
    ifsc_code: Optional[str] = Form(None),
    upi_id: Optional[str] = Form(None),
    commission_per_student: Optional[float] = Form(None),
    commission_type: Optional[str] = Form(None),
    commission_value: Optional[float] = Form(None),
    password: Optional[str] = Form(None),
    profile_photo: Optional[UploadFile] = File(None),
    profile_photo_path: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    counsellor = db.query(Counsellor).filter_by(counsellor_id=counsellor_id).first()
    if not counsellor:
        raise HTTPException(status_code=404, detail="Counsellor not found")

    update_data = {}
    if full_name is not None:
        update_data["full_name"] = full_name
    if phone_no is not None:
        update_data["phone_no"] = phone_no
    if email is not None:
        update_data["email"] = email
    if alternative_phone_no is not None:
        update_data["alternative_phone_no"] = alternative_phone_no
    if address is not None:
        update_data["address"] = address
    if qualification is not None:
        update_data["qualification"] = qualification
    if experience is not None:
        update_data["experience"] = experience
    if bank_account_no is not None:
        update_data["bank_account_no"] = bank_account_no
    if bank_account_name is not None:
        update_data["bank_account_name"] = bank_account_name
    if branch_name is not None:
        update_data["branch_name"] = branch_name
    if ifsc_code is not None:
        update_data["ifsc_code"] = ifsc_code
    if upi_id is not None:
        update_data["upi_id"] = upi_id
    if commission_per_student is not None:
        update_data["commission_per_student"] = commission_per_student
    if commission_type is not None:
        update_data["commission_type"] = commission_type
    if commission_value is not None:
        update_data["commission_value"] = commission_value
    if password is not None:
        update_data["password"] = password

    if per_courses_commission is not None:
        try:
            commission_map = json.loads(per_courses_commission)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid per_courses_commission format. Provide JSON mapping of course_id to percentage.")
        commission_map = validate_and_get_course_details(db, commission_map)
        update_data["per_courses_commission"] = commission_map

    for k, v in update_data.items():
        setattr(counsellor, k, v)

    # profile photo: prefer uploaded file, fallback to provided path string
    if profile_photo:
        uploads_dir = Path("uploads") / "counsellor" / counsellor_id
        uploads_dir.mkdir(parents=True, exist_ok=True)
        file_ext = os.path.splitext(profile_photo.filename)[1]
        file_name = f"profile{file_ext}"
        file_path = uploads_dir / file_name
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(profile_photo.file, buffer)
        counsellor.profile_photo = os.path.relpath(str(file_path), os.getcwd())
    elif profile_photo_path:
        counsellor.profile_photo = profile_photo_path

    counsellor.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(counsellor)

    profile_photo_path = None
    if counsellor.profile_photo:
        try:
            profile_photo_path = os.path.relpath(str(Path(counsellor.profile_photo)), os.getcwd())
        except Exception:
            profile_photo_path = counsellor.profile_photo

    per_courses_commission_out = format_per_courses_commission_for_output(db, counsellor.per_courses_commission)

    return CounsellorOut(**{**counsellor.__dict__, "profile_photo": profile_photo_path, "per_courses_commission": per_courses_commission_out})

# Delete counsellor by ID
@router.delete("/delete-by/{counsellor_id}", response_model=dict)
def delete_counsellor(counsellor_id: str, db: Session = Depends(get_db)):
    counsellor = db.query(Counsellor).filter_by(counsellor_id=counsellor_id).first()
    if not counsellor:
        raise HTTPException(status_code=404, detail="Counsellor not found")
    # remove uploads
    uploads_dir = Path("uploads") / "counsellor" / counsellor_id
    if uploads_dir.exists():
        shutil.rmtree(uploads_dir)
    # delete related admission enquiries first (they reference admission_code and counsellor)
    enquiries = db.query(AdmissionEnquiry).filter_by(counsellor_id=counsellor_id).all()
    for e in enquiries:
        db.delete(e)

    # delete admission codes associated with this counsellor
    codes = db.query(AdmissionCode).filter_by(counsellor_id=counsellor_id).all()
    for ac in codes:
        db.delete(ac)

    # delete commission slips and their files
    try:
        commissions = db.query(CommissionSlip).filter_by(counsellor_id=counsellor_id).all()
        for cs in commissions:
            if cs.file_path and Path(cs.file_path).exists():
                try:
                    Path(cs.file_path).unlink()
                except Exception:
                    pass
            db.delete(cs)
    except Exception:
        # commission model may not exist in older setups; ignore if not present
        pass

    db.delete(counsellor)
    db.commit()
    return {"detail": "Counsellor deleted"}

# Bulk delete counsellors
@router.delete("/bulk-delete", response_model=dict)
def bulk_delete_counsellors(ids: List[str] = Query(...), db: Session = Depends(get_db)):
    counsellors = db.query(Counsellor).filter(Counsellor.counsellor_id.in_(ids)).all()
    for c in counsellors:
        uploads_dir = Path("uploads") / "counsellor" / c.counsellor_id
        if uploads_dir.exists():
            shutil.rmtree(uploads_dir)
        db.delete(c)
    db.commit()
    return {"detail": f"Deleted {len(counsellors)} counsellor(s)"}
