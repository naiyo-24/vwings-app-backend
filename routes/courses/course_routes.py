from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel, validator
from datetime import datetime
from typing import List, Optional, Dict, Any
import os
import shutil
from pathlib import Path

from db import get_db
from models.courses.course_models import Course
from services.course_id_generator import generate_course_id
from routes.notification.notification_routes import create_notification

router = APIRouter(
    prefix="/api/courses",
    tags=["Courses"]
)

# Base directory for uploads (relative to project root)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOADS_DIR = BASE_DIR / "uploads" / "courses"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Pydantic models
class CategoryData(BaseModel):
    job_roles_offered: str
    placement_assistance: bool
    placement_type: str  # "Assisted" or "Guaranteed"
    placement_rate: float
    advantages_highlights: str
    course_fees: float
    created_at: str = None
    updated_at: str = None
    active_status: bool = True
    
    @validator('placement_type')
    def validate_placement_type(cls, v):
        if v not in ["Assisted", "Guaranteed"]:
            raise ValueError('placement_type must be "Assisted" or "Guaranteed"')
        return v

class CourseCreate(BaseModel):
    course_name: str
    course_description: Optional[str] = None
    course_code: str
    weight_requirements: Optional[str] = None
    height_requirements: Optional[str] = None
    vision_standards: Optional[str] = None
    medical_requirements: Optional[str] = None
    min_educational_qualification: Optional[str] = None
    age_criteria: Optional[str] = None
    internship_included: bool = False
    installment_available: bool = False
    installment_policy: Optional[str] = None
    general_data: Optional[CategoryData] = None
    executive_data: Optional[CategoryData] = None

class CourseUpdate(BaseModel):
    course_name: Optional[str] = None
    course_description: Optional[str] = None
    course_code: Optional[str] = None
    weight_requirements: Optional[str] = None
    height_requirements: Optional[str] = None
    vision_standards: Optional[str] = None
    medical_requirements: Optional[str] = None
    min_educational_qualification: Optional[str] = None
    age_criteria: Optional[str] = None
    internship_included: Optional[bool] = None
    installment_available: Optional[bool] = None
    installment_policy: Optional[str] = None
    general_data: Optional[Dict[str, Any]] = None
    executive_data: Optional[Dict[str, Any]] = None

class CourseResponse(BaseModel):
    course_id: str
    course_name: str
    course_description: Optional[str]
    course_code: str
    weight_requirements: Optional[str]
    height_requirements: Optional[str]
    vision_standards: Optional[str]
    medical_requirements: Optional[str]
    min_educational_qualification: Optional[str]
    age_criteria: Optional[str]
    internship_included: bool
    installment_available: bool
    installment_policy: Optional[str]
    course_photo: Optional[str]
    course_video: Optional[str]
    general_data: Optional[Dict[str, Any]]
    executive_data: Optional[Dict[str, Any]]
    
    class Config:
        from_attributes = True

class BulkDeleteRequest(BaseModel):
    course_ids: List[str]

# Helper function to save uploaded file
def save_upload_file(upload_file: UploadFile, course_id: str, file_type: str) -> str:
    """
    Save uploaded file to /uploads/courses/{course_id}/
    Returns the relative file path
    """
    course_dir = UPLOADS_DIR / course_id
    course_dir.mkdir(parents=True, exist_ok=True)
    file_extension = Path(upload_file.filename).suffix
    file_name = f"{file_type}{file_extension}"
    file_path = course_dir / file_name
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    # Return relative path from BACKEND directory
    rel_path = os.path.relpath(file_path, BASE_DIR)
    return rel_path

# API Endpoints
@router.post("/create", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
def create_course(
    course_data: str = Form(...),  # JSON string
    course_photo: Optional[UploadFile] = File(None),
    course_video: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Create a new course with optional photo and video uploads
    """
    import json
    try:
        course_dict = json.loads(course_data)
        course = CourseCreate(**course_dict)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid course data: {str(e)}"
        )
    # Check if course with same code already exists
    existing_course = db.query(Course).filter(Course.course_code == course.course_code).first()
    if existing_course:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course code already exists"
        )
    course_id = generate_course_id()
    # Add timestamps to category data
    general_data = course.general_data.dict() if course.general_data else None
    executive_data = course.executive_data.dict() if course.executive_data else None
    now = datetime.utcnow().isoformat()
    if general_data:
        general_data["created_at"] = now
        general_data["updated_at"] = now
    if executive_data:
        executive_data["created_at"] = now
        executive_data["updated_at"] = now
    new_course = Course(
        course_id=course_id,
        course_name=course.course_name,
        course_description=course.course_description,
        course_code=course.course_code,
        weight_requirements=course.weight_requirements,
        height_requirements=course.height_requirements,
        vision_standards=course.vision_standards,
        medical_requirements=course.medical_requirements,
        min_educational_qualification=course.min_educational_qualification,
        age_criteria=course.age_criteria,
        internship_included=course.internship_included,
        installment_available=course.installment_available,
        installment_policy=course.installment_policy,
        general_data=general_data,
        executive_data=executive_data
    )
    if course_photo:
        new_course.course_photo = save_upload_file(course_photo, course_id, "photo")
    if course_video:
        new_course.course_video = save_upload_file(course_video, course_id, "video")
    db.add(new_course)
    db.commit()
    db.refresh(new_course)
    
    # Notify all students, teachers, and counsellors
    create_notification(
        "New Course Available! 🎓", 
        f"We just added '{new_course.course_name}'. Check it out now!", 
        "student"
    )
    create_notification(
        "New Course Created", 
        f"Course '{new_course.course_name}' has been successfully created.", 
        "admin"
    )
    create_notification(
        "New Course Catalog", 
        f"You can now assign students to '{new_course.course_name}'.", 
        "counsellor"
    )

    return new_course

@router.get("/get-all", response_model=List[CourseResponse])
def get_all_courses(
    skip: int = 0,
    limit: int = 100,
    sort_by_general_fees: bool = True,
    min_fee: Optional[float] = None,
    max_fee: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """
    Get all courses with optional filters (min_fee, max_fee) and optional sorting by general fees.
    Filtering and sorting operate on `general_data.course_fees`.
    """
    import json
    query = db.query(Course)
    # Load all rows into memory to support filtering on JSON-like `general_data` field
    courses = query.all()

    def _get_fees(c):
        try:
            g = c.general_data or {}
            if isinstance(g, str):
                g = json.loads(g)
            return float(g.get("course_fees") or 0)
        except Exception:
            return 0.0

    # Apply min/max fee filters (if provided)
    if min_fee is not None or max_fee is not None:
        filtered = []
        for c in courses:
            fee = _get_fees(c)
            if min_fee is not None and fee < min_fee:
                continue
            if max_fee is not None and fee > max_fee:
                continue
            filtered.append(c)
        courses = filtered

    # Apply sorting by general fees (descending) by default
    if sort_by_general_fees:
        courses.sort(key=_get_fees, reverse=True)

    # apply pagination after filtering/sorting
    if limit is not None:
        courses = courses[skip: skip + limit]
    else:
        courses = courses[skip:]
    # Convert absolute paths to relative for response
    for c in courses:
        if c.course_photo and os.path.isabs(c.course_photo):
            c.course_photo = os.path.relpath(c.course_photo, BASE_DIR)
        if c.course_video and os.path.isabs(c.course_video):
            c.course_video = os.path.relpath(c.course_video, BASE_DIR)
    return courses

@router.get("/get-by/{course_id}", response_model=CourseResponse)
def get_course_by_id(course_id: str, db: Session = Depends(get_db)):
    """
    Get a single course by ID
    """
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    if course.course_photo and os.path.isabs(course.course_photo):
        course.course_photo = os.path.relpath(course.course_photo, BASE_DIR)
    if course.course_video and os.path.isabs(course.course_video):
        course.course_video = os.path.relpath(course.course_video, BASE_DIR)
    return course

@router.put("/put-by/{course_id}", response_model=CourseResponse)
def update_course(
    course_id: str,
    course_data: Optional[str] = Form(None),  # JSON string
    course_photo: Optional[UploadFile] = File(None),
    course_video: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Update a course by ID. Can update any field(s)
    """
    import json
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    if course_data:
        try:
            update_dict = json.loads(course_data)
            update = CourseUpdate(**update_dict)
            for field, value in update.dict(exclude_unset=True).items():
                if field in ["general_data", "executive_data"] and value is not None:
                    existing_data = getattr(course, field) or {}
                    updated_data = {**existing_data, **value}
                    updated_data["updated_at"] = datetime.utcnow().isoformat()
                    setattr(course, field, updated_data)
                elif value is not None:
                    setattr(course, field, value)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid update data: {str(e)}"
            )
    if course_photo:
        old_photo_path = BASE_DIR / course.course_photo if course.course_photo else None
        if old_photo_path and old_photo_path.exists():
            os.remove(old_photo_path)
        course.course_photo = save_upload_file(course_photo, course_id, "photo")
    if course_video:
        old_video_path = BASE_DIR / course.course_video if course.course_video else None
        if old_video_path and old_video_path.exists():
            os.remove(old_video_path)
        course.course_video = save_upload_file(course_video, course_id, "video")
    db.commit()
    db.refresh(course)
    return course

@router.delete("/delete-by/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: str, db: Session = Depends(get_db)):
    """
    Delete a course by ID
    """
    course = db.query(Course).filter(Course.course_id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    # Delete uploaded files
    course_dir = UPLOADS_DIR / course_id
    if course_dir.exists():
        shutil.rmtree(course_dir)
    db.delete(course)
    db.commit()
    return None

@router.delete("/bulk/delete", status_code=status.HTTP_200_OK)
def bulk_delete_courses(request: BulkDeleteRequest, db: Session = Depends(get_db)):
    """
    Delete multiple courses by IDs
    """
    deleted_count = 0
    not_found = []
    for course_id in request.course_ids:
        course = db.query(Course).filter(Course.course_id == course_id).first()
        if course:
            # Delete uploaded files
            course_dir = UPLOADS_DIR / course_id
            if course_dir.exists():
                shutil.rmtree(course_dir)
            db.delete(course)
            deleted_count += 1
        else:
            not_found.append(course_id)
    db.commit()
    return {
        "message": f"Deleted {deleted_count} course(s)",
        "deleted_count": deleted_count,
        "not_found": not_found
    }
