from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from db import get_db

from models.auth.student_models import Student
from models.auth.teacher_models import Teacher
from models.auth.counsellor_models import Counsellor
from models.courses.course_models import Course

router = APIRouter(prefix="/search", tags=["Search"])

@router.get("/")
def global_search(
    q: str = Query(..., min_length=1, description="Search query string"),
    type: Optional[str] = Query(None, description="Optional filter by type (student, teacher, counsellor, course)"),
    db: Session = Depends(get_db)
):
    results = {
        "students": [],
        "teachers": [],
        "counsellors": [],
        "courses": []
    }
    
    search_term = f"%{q}%"

    if not type or type == "student":
        students = db.query(Student).filter(
            or_(
                Student.full_name.ilike(search_term),
                Student.email.ilike(search_term),
                Student.student_id.ilike(search_term),
                Student.phone_no.ilike(search_term)
            )
        ).limit(10).all()
        for s in students:
            results["students"].append({
                "id": s.student_id,
                "name": s.full_name,
                "email": s.email,
                "phone_no": s.phone_no,
                "type": "student",
                "photo": s.profile_photo
            })

    if not type or type == "teacher":
        teachers = db.query(Teacher).filter(
            or_(
                Teacher.full_name.ilike(search_term),
                Teacher.email.ilike(search_term),
                Teacher.teacher_id.ilike(search_term),
                Teacher.phone_no.ilike(search_term)
            )
        ).limit(10).all()
        for t in teachers:
            results["teachers"].append({
                "id": t.teacher_id,
                "name": t.full_name,
                "email": t.email,
                "phone_no": t.phone_no,
                "type": "teacher",
                "photo": t.profile_photo
            })

    if not type or type == "counsellor":
        counsellors = db.query(Counsellor).filter(
            or_(
                Counsellor.full_name.ilike(search_term),
                Counsellor.email.ilike(search_term),
                Counsellor.counsellor_id.ilike(search_term),
                Counsellor.phone_no.ilike(search_term)
            )
        ).limit(10).all()
        for c in counsellors:
            results["counsellors"].append({
                "id": c.counsellor_id,
                "name": c.full_name,
                "email": c.email,
                "phone_no": c.phone_no,
                "type": "counsellor",
                "photo": c.profile_photo
            })

    if not type or type == "course":
        courses = db.query(Course).filter(
            or_(
                Course.course_name.ilike(search_term),
                Course.course_code.ilike(search_term),
                Course.course_id.ilike(search_term)
            )
        ).limit(10).all()
        for c in courses:
            results["courses"].append({
                "id": c.course_id,
                "name": c.course_name,
                "code": c.course_code,
                "type": "course",
                "photo": c.course_photo
            })

    return {"success": True, "data": results}
