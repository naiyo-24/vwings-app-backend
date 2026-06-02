from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Form
from sqlalchemy.orm import Session
import os
import json
from db import get_db
from models.classroom.classroom_models import Classroom
from models.auth.student_models import Student
from models.auth.teacher_models import Teacher
from models.announcement.announcement_models import Announcement
from services.class_id_generator import generate_class_id
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel


# Pydantic Schemas
class ClassroomCreate(BaseModel):
    class_name: str
    class_description: Optional[str] = None
    teacher_ids: Optional[List[str]] = None
    student_ids: Optional[List[str]] = None
    admin_id: Optional[str] = None


class ClassroomResponse(BaseModel):
    class_id: str
    class_name: str
    class_description: Optional[str] = None
    class_photo: Optional[str] = None
    meet_link: Optional[str] = None
    class_date: Optional[str] = None
    class_time: Optional[str] = None
    teacher_ids: Optional[List[str]] = None
    student_ids: Optional[List[str]] = None
    teacher_details: Optional[List[dict]] = None
    student_details: Optional[List[dict]] = None
    admin_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


router = APIRouter(prefix="/api/classrooms", tags=["Classrooms"])

# Directory to store uploaded class photos
UPLOAD_DIR = "uploads/classrooms"


# Helper to save photo
async def save_class_photo(class_id: str, photo: UploadFile):
    dir_path = os.path.join(UPLOAD_DIR, class_id)
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, photo.filename)
    with open(file_path, "wb") as f:
        f.write(await photo.read())
    return file_path


# Helper to fetch person summaries (id + full_name) preserving given order
def _person_summaries(db: Session, model, id_attr: str, ids: Optional[List[str]]):
    if not ids:
        return []
    rows = db.query(model).filter(getattr(model, id_attr).in_(ids)).all()
    mapping = {getattr(r, id_attr): getattr(r, 'full_name', None) for r in rows}
    return [{"id": i, "full_name": mapping.get(i)} for i in ids]

# Create a new classroom endpoint
@router.post("/create", response_model=ClassroomResponse)
async def create_classroom(
    class_name: str = Form(...),
    class_description: str = Form(None),
    teacher_ids: Optional[str] = Form(None),  # JSON string
    student_ids: Optional[str] = Form(None),  # JSON string
    class_date: Optional[str] = Form(None),
    class_time: Optional[str] = Form(None),
    admin_id: Optional[str] = Form(None),
    photo: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    try:
        class_id = generate_class_id(class_name)
        photo_path = None
        if photo:
            photo_path = await save_class_photo(class_id, photo)

        # parse json lists if provided
        t_ids = json.loads(teacher_ids) if teacher_ids else None
        s_ids = json.loads(student_ids) if student_ids else None

        classroom = Classroom(
            class_id=class_id,
            class_name=class_name,
            class_description=class_description,
            class_photo=photo_path,
            meet_link=None,
            class_date=class_date,
            class_time=class_time,
            teacher_ids=t_ids,
            student_ids=s_ids,
            admin_id=admin_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(classroom)
        db.commit()
        db.refresh(classroom)
        return {
            **{k: getattr(classroom, k) for k in [
                'class_id', 'class_name', 'class_description', 'class_photo', 'meet_link', 'class_date', 'class_time', 'teacher_ids', 'student_ids', 'admin_id', 'created_at', 'updated_at'
            ]},
            'teacher_details': _person_summaries(db, Teacher, 'teacher_id', classroom.teacher_ids),
            'student_details': _person_summaries(db, Student, 'student_id', classroom.student_ids),
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating classroom: {str(e)}")

# Get all classrooms
@router.get("/get-all", response_model=List[ClassroomResponse])
def get_all_classrooms(db: Session = Depends(get_db)):
    classrooms = db.query(Classroom).all()
    result = []
    for c in classrooms:
        result.append({
            **{k: getattr(c, k) for k in [
                'class_id', 'class_name', 'class_description', 'class_photo', 'meet_link', 'class_date', 'class_time', 'teacher_ids', 'student_ids', 'admin_id', 'created_at', 'updated_at'
            ]},
            'teacher_details': _person_summaries(db, Teacher, 'teacher_id', c.teacher_ids),
            'student_details': _person_summaries(db, Student, 'student_id', c.student_ids),
        })
    return result

# Get classroom by ID
@router.get("/get-by/{class_id}", response_model=ClassroomResponse)
def get_classroom_by_id(class_id: str, db: Session = Depends(get_db)):
    classroom = db.query(Classroom).filter(Classroom.class_id == class_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")
    return {
        **{k: getattr(classroom, k) for k in [
            'class_id', 'class_name', 'class_description', 'class_photo', 'meet_link', 'class_date', 'class_time', 'teacher_ids', 'student_ids', 'admin_id', 'created_at', 'updated_at'
        ]},
        'teacher_details': _person_summaries(db, Teacher, 'teacher_id', classroom.teacher_ids),
        'student_details': _person_summaries(db, Student, 'student_id', classroom.student_ids),
    }

# Get classrooms by teacher_id
@router.get("/get/by-teacher/{teacher_id}", response_model=List[ClassroomResponse])
def get_classrooms_by_teacher(teacher_id: str, db: Session = Depends(get_db)):
    classrooms = db.query(Classroom).all()
    result = []
    for c in classrooms:
        if c.teacher_ids and teacher_id in (c.teacher_ids or []):
            result.append({
                **{k: getattr(c, k) for k in [
                    'class_id', 'class_name', 'class_description', 'class_photo', 'meet_link', 'class_date', 'class_time', 'teacher_ids', 'student_ids', 'admin_id', 'created_at', 'updated_at'
                ]},
                'teacher_details': _person_summaries(db, Teacher, 'teacher_id', c.teacher_ids),
                'student_details': _person_summaries(db, Student, 'student_id', c.student_ids),
            })
    return result

# Get classrooms by student_id
@router.get("/get/by-student/{student_id}", response_model=List[ClassroomResponse])
def get_classrooms_by_student(student_id: str, db: Session = Depends(get_db)):
    classrooms = db.query(Classroom).all()
    result = []
    for c in classrooms:
        if c.student_ids and student_id in (c.student_ids or []):
            result.append({
                **{k: getattr(c, k) for k in [
                    'class_id', 'class_name', 'class_description', 'class_photo', 'meet_link', 'class_date', 'class_time', 'teacher_ids', 'student_ids', 'admin_id', 'created_at', 'updated_at'
                ]},
                'teacher_details': _person_summaries(db, Teacher, 'teacher_id', c.teacher_ids),
                'student_details': _person_summaries(db, Student, 'student_id', c.student_ids),
            })
    return result

# Get classrooms by admin_id
@router.get("/get/by-admin/{admin_id}", response_model=List[ClassroomResponse])
def get_classrooms_by_admin(admin_id: str, db: Session = Depends(get_db)):
    classrooms = db.query(Classroom).filter(Classroom.admin_id == admin_id).all()
    result = []
    for c in classrooms:
        result.append({
            **{k: getattr(c, k) for k in [
                'class_id', 'class_name', 'class_description', 'class_photo', 'meet_link', 'class_date', 'class_time', 'teacher_ids', 'student_ids', 'admin_id', 'created_at', 'updated_at'
            ]},
            'teacher_details': _person_summaries(db, Teacher, 'teacher_id', c.teacher_ids),
            'student_details': _person_summaries(db, Student, 'student_id', c.student_ids),
        })
    return result

# Update classroom by teacher
@router.put("/update-by/teacher/{teacher_id}/{class_id}", response_model=ClassroomResponse)
async def update_classroom_by_teacher(
    teacher_id: str,
    class_id: str,
    class_name: Optional[str] = Form(None),
    class_description: Optional[str] = Form(None),
    student_ids: Optional[str] = Form(None),  # JSON string
    photo: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    classroom = db.query(Classroom).filter(Classroom.class_id == class_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")
    if not classroom.teacher_ids or teacher_id not in (classroom.teacher_ids or []):
        raise HTTPException(status_code=403, detail="Teacher not authorized to update this classroom")

    if class_name is not None:
        classroom.class_name = class_name
    if class_description is not None:
        classroom.class_description = class_description
    if student_ids is not None:
        new_student_ids = json.loads(student_ids)
        existing_student_ids = classroom.student_ids or []
        added_students = list(set(new_student_ids) - set(existing_student_ids))
        
        classroom.student_ids = new_student_ids
        
        if added_students:
            teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()
            teacher_name = teacher.full_name if teacher else "a teacher"
            for s_id in added_students:
                headline = f"New Classroom Assigned: {classroom.class_name}"
                description = f"You have been assigned to {classroom.class_name} by {teacher_name}. Please check your Classrooms tab for upcoming sessions."
                ann = Announcement(
                    headline=headline,
                    description=description,
                    role="student",
                    target_id=s_id,
                    active_status=True
                )
                db.add(ann)
    if photo:
        photo_path = await save_class_photo(class_id, photo)
        classroom.class_photo = photo_path
    classroom.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(classroom)
    return {
        **{k: getattr(classroom, k) for k in [
            'class_id', 'class_name', 'class_description', 'class_photo', 'meet_link', 'class_date', 'class_time', 'teacher_ids', 'student_ids', 'admin_id', 'created_at', 'updated_at'
        ]},
        'teacher_details': _person_summaries(db, Teacher, 'teacher_id', classroom.teacher_ids),
        'student_details': _person_summaries(db, Student, 'student_id', classroom.student_ids),
    }

# Update classroom by admin
@router.put("/update-by/admin/{admin_id}/{class_id}", response_model=ClassroomResponse)
async def update_classroom_by_admin(
    admin_id: str,
    class_id: str,
    class_name: Optional[str] = Form(None),
    class_description: Optional[str] = Form(None),
    teacher_ids: Optional[str] = Form(None),
    student_ids: Optional[str] = Form(None),
    photo: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    classroom = db.query(Classroom).filter(Classroom.class_id == class_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")
    if classroom.admin_id != admin_id:
        raise HTTPException(status_code=403, detail="Admin not authorized to update this classroom")

    if class_name is not None:
        classroom.class_name = class_name
    if class_description is not None:
        classroom.class_description = class_description
    if teacher_ids is not None:
        classroom.teacher_ids = json.loads(teacher_ids)
    if student_ids is not None:
        classroom.student_ids = json.loads(student_ids)
    if photo:
        photo_path = await save_class_photo(class_id, photo)
        classroom.class_photo = photo_path
    classroom.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(classroom)
    return {
        **{k: getattr(classroom, k) for k in [
            'class_id', 'class_name', 'class_description', 'class_photo', 'meet_link', 'class_date', 'class_time', 'teacher_ids', 'student_ids', 'admin_id', 'created_at', 'updated_at'
        ]},
        'teacher_details': _person_summaries(db, Teacher, 'teacher_id', classroom.teacher_ids),
        'student_details': _person_summaries(db, Student, 'student_id', classroom.student_ids),
    }

class MeetLinkUpdate(BaseModel):
    meet_link: str

# Update classroom meet link
@router.put("/update-meet-link/{class_id}", response_model=ClassroomResponse)
def update_classroom_meet_link(class_id: str, payload: MeetLinkUpdate, db: Session = Depends(get_db)):
    classroom = db.query(Classroom).filter(Classroom.class_id == class_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")
    
    classroom.meet_link = payload.meet_link
    classroom.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(classroom)
    return {
        **{k: getattr(classroom, k) for k in [
            'class_id', 'class_name', 'class_description', 'class_photo', 'meet_link', 'class_date', 'class_time', 'teacher_ids', 'student_ids', 'admin_id', 'created_at', 'updated_at'
        ]},
        'teacher_details': _person_summaries(db, Teacher, 'teacher_id', classroom.teacher_ids),
        'student_details': _person_summaries(db, Student, 'student_id', classroom.student_ids),
    }

# Delete classroom by admin
@router.delete("/delete-by/admin/{admin_id}/{class_id}")
def delete_classroom_by_admin(admin_id: str, class_id: str, db: Session = Depends(get_db)):
    classroom = db.query(Classroom).filter(Classroom.class_id == class_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")
    if classroom.admin_id != admin_id:
        raise HTTPException(status_code=403, detail="Admin not authorized to delete this classroom")
    db.delete(classroom)
    db.commit()
    dir_path = os.path.join(UPLOAD_DIR, class_id)
    if os.path.exists(dir_path):
        import shutil
        shutil.rmtree(dir_path)
    return {"message": "Classroom deleted"}

# Delete classroom by teacher
@router.delete("/delete-by/teacher/{teacher_id}/{class_id}")
def delete_classroom_by_teacher(teacher_id: str, class_id: str, db: Session = Depends(get_db)):
    classroom = db.query(Classroom).filter(Classroom.class_id == class_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")
    if not classroom.teacher_ids or teacher_id not in (classroom.teacher_ids or []):
        raise HTTPException(status_code=403, detail="Teacher not authorized to delete this classroom")
    db.delete(classroom)
    db.commit()
    dir_path = os.path.join(UPLOAD_DIR, class_id)
    if os.path.exists(dir_path):
        import shutil
        shutil.rmtree(dir_path)
    return {"message": "Classroom deleted"}

# Bulk delete classrooms
class BulkDeleteRequest(BaseModel):
    class_ids: List[str]

# Bulk delete classrooms endpoint
@router.delete("/delete/bulk")
def delete_classrooms_bulk(request: BulkDeleteRequest, db: Session = Depends(get_db)):
    deleted = 0
    for class_id in request.class_ids:
        classroom = db.query(Classroom).filter(Classroom.class_id == class_id).first()
        if classroom:
            db.delete(classroom)
            dir_path = os.path.join(UPLOAD_DIR, class_id)
            if os.path.exists(dir_path):
                import shutil
                shutil.rmtree(dir_path)
            deleted += 1
    db.commit()
    return {"message": f"Deleted {deleted} classrooms"}

# Remove students from classroom endpoint
class RemoveStudentsRequest(BaseModel):
    student_ids: List[str]


@router.post("/remove-students/{class_id}")
def remove_students_from_class(
    class_id: str,
    body: RemoveStudentsRequest,
    requester_id: str,
    db: Session = Depends(get_db),
):
    """Remove one or more student IDs from a classroom.

    - `requester_id` must be the class `admin_id` or one of the `teacher_ids`.
    - `body.student_ids` is a JSON array of student IDs to remove.
    """
    classroom = db.query(Classroom).filter(Classroom.class_id == class_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")

    # authorize: must be admin or teacher for this class
    is_admin = classroom.admin_id == requester_id
    is_teacher = bool(classroom.teacher_ids and requester_id in (classroom.teacher_ids or []))
    if not (is_admin or is_teacher):
        raise HTTPException(status_code=403, detail="Not authorized to remove students from this classroom")

    existing = classroom.student_ids or []
    removed = []
    for sid in body.student_ids:
        if sid in existing:
            existing.remove(sid)
            removed.append(sid)

    # perform direct update to ensure DB value is overwritten
    db.query(Classroom).filter(Classroom.class_id == class_id).update({
        Classroom.student_ids: existing,
        Classroom.updated_at: datetime.utcnow()
    })
    db.commit()

    # return canonical current state
    updated = db.query(Classroom).filter(Classroom.class_id == class_id).first()
    return {"class_id": class_id, "removed": removed, "remaining_count": len(updated.student_ids or [])}
