from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import traceback

from db import get_db
from models.admission.admission_enquiry_models import AdmissionEnquiry
from models.auth.counsellor_models import Counsellor
from models.admission.admission_code_models import AdmissionCode
from models.courses.course_models import Course
from services.admission_enquiry_id_generator import generate_admission_enquiry_id
from models.auth.student_models import Student
from services.student_id_generator import generate_student_id

router = APIRouter(prefix="/api/admission-enquiries", tags=["AdmissionEnquiries"])


class AdmissionEnquiryBase(BaseModel):
    student_name: str
    student_phn_no: str
    student_alternative_phn_no: Optional[str] = None
    student_email: Optional[EmailStr] = None
    student_address: Optional[str] = None
    course_id: str
    course_category: Optional[str] = "general"
    guardian_name: Optional[str] = None
    guardian_phn_no: Optional[str] = None
    fit_medically: Optional[bool] = False
    meets_height_requirements: Optional[bool] = False
    meets_weight_requirements: Optional[bool] = False
    meets_vision_standards: Optional[bool] = False
    counsellor_id: str
    admission_code: str
    status: Optional[str] = "pending"  # converted/contacted/cancelled/pending


class AdmissionEnquiryCreate(AdmissionEnquiryBase):
    pass


class AdmissionEnquiryUpdate(BaseModel):
    student_name: Optional[str] = None
    student_phn_no: Optional[str] = None
    student_alternative_phn_no: Optional[str] = None
    student_email: Optional[EmailStr] = None
    student_address: Optional[str] = None
    guardian_name: Optional[str] = None
    guardian_phn_no: Optional[str] = None
    fit_medically: Optional[bool] = None
    meets_height_requirements: Optional[bool] = None
    meets_weight_requirements: Optional[bool] = None
    meets_vision_standards: Optional[bool] = None
    counsellor_id: Optional[str] = None
    admission_code: Optional[str] = None
    course_id: Optional[str] = None
    course_category: Optional[str] = None
    status: Optional[str] = None


class AdmissionEnquiryResponse(AdmissionEnquiryBase):
    enquiry_id: str
    created_at: datetime
    updated_at: datetime
    course_name: Optional[str] = None
    counsellor_name: Optional[str] = None
    course_category: Optional[str] = "general"

    class Config:
        from_attributes = True


@router.post("/create", response_model=AdmissionEnquiryResponse, status_code=status.HTTP_201_CREATED)
def create_admission_enquiry(payload: AdmissionEnquiryCreate, db: Session = Depends(get_db)):
    # validate counsellor
    counsellor = db.query(Counsellor).filter_by(counsellor_id=payload.counsellor_id).first()
    if not counsellor:
        raise HTTPException(status_code=404, detail="Counsellor not found")

    # validate admission code (mandatory) and ownership
    ac = db.query(AdmissionCode).filter_by(admission_code=payload.admission_code).first()
    if not ac:
        raise HTTPException(status_code=404, detail="Admission code not found")
    if ac.counsellor_id != payload.counsellor_id:
        raise HTTPException(status_code=403, detail="Admission code not assigned to this counsellor")

    # validate course (mandatory)
    course = db.query(Course).filter_by(course_id=payload.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    now = datetime.utcnow()
    enquiry_id = generate_admission_enquiry_id(now)

    # ensure unique enquiry_id
    while db.query(AdmissionEnquiry).filter_by(enquiry_id=enquiry_id).first():
        now = datetime.utcnow()
        enquiry_id = generate_admission_enquiry_id(now)

    enq = AdmissionEnquiry(
        enquiry_id=enquiry_id,
        counsellor_id=payload.counsellor_id,
        student_name=payload.student_name,
        student_phn_no=payload.student_phn_no,
        student_alternative_phn_no=payload.student_alternative_phn_no,
        student_email=str(payload.student_email) if payload.student_email else None,
        student_address=payload.student_address,
        guardian_name=payload.guardian_name,
        guardian_phn_no=payload.guardian_phn_no,
        fit_medically=payload.fit_medically or False,
        meets_height_requirements=payload.meets_height_requirements or False,
        meets_weight_requirements=payload.meets_weight_requirements or False,
        meets_vision_standards=payload.meets_vision_standards or False,
        admission_code=payload.admission_code,
        course_id=payload.course_id,
        course_category=payload.course_category if hasattr(payload, 'course_category') else None,
        status=payload.status if payload.status else "pending",
        created_at=now,
        updated_at=now,
    )
    db.add(enq)
    
    # If the enquiry is being created as 'converted', create the student as well
    if enq.status == "converted":
        student_id = generate_student_id(now)
        student_email = str(payload.student_email) if payload.student_email else f"{student_id.lower()}@vwings.com"
        
        # Check if email is already taken
        existing_student = db.query(Student).filter_by(email=student_email).first()
        if not existing_student:
            new_student = Student(
                student_id=student_id,
                full_name=payload.student_name,
                phone_no=payload.student_phn_no,
                email=student_email,
                address=payload.student_address or "N/A",
                guardian_name=payload.guardian_name or "N/A",
                guardian_mobile_no=payload.guardian_phn_no or "N/A",
                course_availing=payload.course_id,
                password=payload.student_phn_no, # Default password is phone number
                created_at=now,
                updated_at=now
            )
            db.add(new_student)

    db.commit()
    db.refresh(enq)
    data = {k: v for k, v in enq.__dict__.items() if not k.startswith("_")}
    course = db.query(Course).filter_by(course_id=data.get("course_id")).first() if data.get("course_id") else None
    counsellor = db.query(Counsellor).filter_by(counsellor_id=data.get("counsellor_id")).first() if data.get("counsellor_id") else None
    data["course_name"] = course.course_name if course else None
    data["counsellor_name"] = counsellor.full_name if counsellor and hasattr(counsellor, "full_name") else None
    data["course_category"] = data.get("course_category")
    print("update_enquiry_status returning data keys:", list(data.keys()))
    return data


@router.get("/get-all", response_model=List[AdmissionEnquiryResponse])
def get_all_enquiries(db: Session = Depends(get_db)):
    items = db.query(AdmissionEnquiry).all()
    result = []
    for item in items:
        data = {k: v for k, v in item.__dict__.items() if not k.startswith("_")}
        # Always fetch latest course and counsellor
        course = db.query(Course).filter_by(course_id=data.get("course_id")).first() if data.get("course_id") else None
        counsellor = db.query(Counsellor).filter_by(counsellor_id=data.get("counsellor_id")).first() if data.get("counsellor_id") else None
        data["course_name"] = course.course_name if course else None
        data["counsellor_name"] = counsellor.full_name if counsellor and hasattr(counsellor, "full_name") else None
        # ensure course_category present (fallback handled by model default)
        data["course_category"] = data.get("course_category")
        result.append(data)
    return result


@router.get("/get-by/{enquiry_id}", response_model=AdmissionEnquiryResponse)
def get_enquiry(enquiry_id: str, db: Session = Depends(get_db)):
    item = db.query(AdmissionEnquiry).filter_by(enquiry_id=enquiry_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Admission enquiry not found")
    data = {k: v for k, v in item.__dict__.items() if not k.startswith("_")}
    # Always fetch latest course and counsellor
    course = db.query(Course).filter_by(course_id=data.get("course_id")).first() if data.get("course_id") else None
    counsellor = db.query(Counsellor).filter_by(counsellor_id=data.get("counsellor_id")).first() if data.get("counsellor_id") else None
    data["course_name"] = course.course_name if course else None
    data["counsellor_name"] = counsellor.full_name if counsellor and hasattr(counsellor, "full_name") else None
    data["course_category"] = data.get("course_category")
    return data

# Define a separate model for status update
class AdmissionEnquiryStatusUpdate(BaseModel):
    status: str

# Separate endpoint to update only the status
@router.put("/update-status/{enquiry_id}", response_model=AdmissionEnquiryResponse)
def update_enquiry_status(enquiry_id: str, payload: AdmissionEnquiryStatusUpdate, db: Session = Depends(get_db)):
    item = db.query(AdmissionEnquiry).filter_by(enquiry_id=enquiry_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Admission enquiry not found")
    # Check if we need to create or delete a student
    if item.status == "converted" and payload.status != "converted":
        # Delete student if it was converted and is now changing to something else
        # Find student by email or phone_no
        search_email = item.student_email if item.student_email else ""
        student = db.query(Student).filter((Student.email == search_email) | (Student.phone_no == item.student_phn_no)).first()
        if student:
            db.delete(student)
            
    elif item.status != "converted" and payload.status == "converted":
        # Create student since status is becoming converted
        student_id = generate_student_id(datetime.utcnow())
        student_email = item.student_email if item.student_email else f"{student_id.lower()}@vwings.com"
        existing_student = db.query(Student).filter((Student.email == student_email) | (Student.phone_no == item.student_phn_no)).first()
        if not existing_student:
            new_student = Student(
                student_id=student_id,
                full_name=item.student_name,
                phone_no=item.student_phn_no,
                email=student_email,
                address=item.student_address or "N/A",
                guardian_name=item.guardian_name or "N/A",
                guardian_mobile_no=item.guardian_phn_no or "N/A",
                course_availing=item.course_id,
                password=item.student_phn_no,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(new_student)

    item.status = payload.status
    item.updated_at = datetime.utcnow()
    db.add(item)
    db.commit()
    db.refresh(item)
    # Build explicit response dict to satisfy response_model
    course = db.query(Course).filter_by(course_id=item.course_id).first() if item.course_id else None
    counsellor = db.query(Counsellor).filter_by(counsellor_id=item.counsellor_id).first() if item.counsellor_id else None

    resp = {
        "student_name": item.student_name,
        "student_phn_no": item.student_phn_no,
        "student_alternative_phn_no": item.student_alternative_phn_no,
        "student_email": item.student_email,
        "student_address": item.student_address,
        "course_id": item.course_id,
        "course_category": item.course_category,
        "guardian_name": item.guardian_name,
        "guardian_phn_no": item.guardian_phn_no,
        "fit_medically": item.fit_medically,
        "meets_height_requirements": item.meets_height_requirements,
        "meets_weight_requirements": item.meets_weight_requirements,
        "meets_vision_standards": item.meets_vision_standards,
        "counsellor_id": item.counsellor_id,
        "admission_code": item.admission_code,
        "status": item.status,
        "enquiry_id": item.enquiry_id,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "course_name": course.course_name if course else None,
        "counsellor_name": counsellor.full_name if counsellor and hasattr(counsellor, "full_name") else None,
    }

    return resp

# Full update of enquiry by ID
@router.put("/put-by/{enquiry_id}", response_model=AdmissionEnquiryResponse)
def update_enquiry(enquiry_id: str, payload: AdmissionEnquiryUpdate, db: Session = Depends(get_db)):
    item = db.query(AdmissionEnquiry).filter_by(enquiry_id=enquiry_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Admission enquiry not found")

    # determine the counsellor that will own this enquiry after update
    new_counsellor_id = payload.counsellor_id if payload.counsellor_id is not None else item.counsellor_id

    # if admission_code is being changed, validate it and ownership against new counsellor
    if payload.admission_code is not None:
        if payload.admission_code:
            ac = db.query(AdmissionCode).filter_by(admission_code=payload.admission_code).first()
            if not ac:
                raise HTTPException(status_code=404, detail="Admission code not found")
            if ac.counsellor_id != new_counsellor_id:
                raise HTTPException(status_code=403, detail="Admission code not assigned to this counsellor")
        item.admission_code = payload.admission_code

    if payload.course_id is not None:
        if payload.course_id:
            course = db.query(Course).filter_by(course_id=payload.course_id).first()
            if not course:
                raise HTTPException(status_code=404, detail="Course not found")
        item.course_id = payload.course_id

    if payload.course_category is not None:
        item.course_category = payload.course_category

    # if counsellor is being changed but admission_code remains, ensure existing code belongs to new counsellor
    if payload.counsellor_id is not None:
        counsellor = db.query(Counsellor).filter_by(counsellor_id=payload.counsellor_id).first()
        if not counsellor:
            raise HTTPException(status_code=404, detail="Counsellor not found")
        # check ownership of existing admission_code
        existing_ac = db.query(AdmissionCode).filter_by(admission_code=item.admission_code).first()
        if existing_ac and existing_ac.counsellor_id != payload.counsellor_id:
            raise HTTPException(status_code=403, detail="Existing admission code not assigned to the new counsellor")
        item.counsellor_id = payload.counsellor_id

    for field, value in payload.dict(exclude_unset=True).items():
        if hasattr(item, field) and field not in ("counsellor_id", "admission_code"):
            setattr(item, field, value)

    # Check if we need to create or delete a student based on status change
    if payload.status is not None and payload.status != item.status:
        if item.status == "converted" and payload.status != "converted":
            search_email = item.student_email if item.student_email else ""
            student = db.query(Student).filter((Student.email == search_email) | (Student.phone_no == item.student_phn_no)).first()
            if student:
                db.delete(student)
        elif item.status != "converted" and payload.status == "converted":
            student_id = generate_student_id(datetime.utcnow())
            student_email = payload.student_email if payload.student_email else (item.student_email if item.student_email else f"{student_id.lower()}@vwings.com")
            student_phn = payload.student_phn_no if payload.student_phn_no else item.student_phn_no
            existing_student = db.query(Student).filter((Student.email == student_email) | (Student.phone_no == student_phn)).first()
            if not existing_student:
                new_student = Student(
                    student_id=student_id,
                    full_name=payload.student_name if payload.student_name else item.student_name,
                    phone_no=student_phn,
                    email=student_email,
                    address=(payload.student_address if payload.student_address else item.student_address) or "N/A",
                    guardian_name=(payload.guardian_name if payload.guardian_name else item.guardian_name) or "N/A",
                    guardian_mobile_no=(payload.guardian_phn_no if payload.guardian_phn_no else item.guardian_phn_no) or "N/A",
                    course_availing=payload.course_id if payload.course_id else item.course_id,
                    password=student_phn,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(new_student)
        
        item.status = payload.status

    item.updated_at = datetime.utcnow()
    db.add(item)
    db.commit()
    db.refresh(item)
    data = {k: v for k, v in item.__dict__.items() if not k.startswith("_")}
    course = db.query(Course).filter_by(course_id=data.get("course_id")).first() if data.get("course_id") else None
    counsellor = db.query(Counsellor).filter_by(counsellor_id=data.get("counsellor_id") ).first() if data.get("counsellor_id") else None
    data["course_name"] = course.course_name if course else None
    data["counsellor_name"] = counsellor.full_name if counsellor and hasattr(counsellor, "full_name") else None
    data["course_category"] = data.get("course_category")
    return data


@router.delete("/delete-by/{enquiry_id}", response_model=dict)
def delete_enquiry(enquiry_id: str, db: Session = Depends(get_db)):
    item = db.query(AdmissionEnquiry).filter_by(enquiry_id=enquiry_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Admission enquiry not found")
    db.delete(item)
    db.commit()
    return {"detail": "Deleted successfully"}
