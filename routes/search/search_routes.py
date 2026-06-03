from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, cast, String
from typing import Optional
from db import get_db

from models.auth.student_models import Student
from models.auth.teacher_models import Teacher
from models.auth.counsellor_models import Counsellor
from models.courses.course_models import Course
from models.fees.fees_models import Fee
from models.salary.salary_models import Salary
from models.commission.commission_models import Payout
from models.announcement.announcement_models import Announcement
from models.ads.ads_models import Advertisement
from models.admission.admission_enquiry_models import AdmissionEnquiry
from models.help_center.help_center_models import HelpCenter

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


@router.get("/table/students")
def search_students_table(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    search_term = f"%{q}%"
    return db.query(Student).filter(
        or_(
            Student.full_name.ilike(search_term),
            Student.email.ilike(search_term),
            Student.student_id.ilike(search_term),
            Student.phone_no.ilike(search_term)
        )
    ).all()

@router.get("/table/teachers")
def search_teachers_table(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    search_term = f"%{q}%"
    return db.query(Teacher).filter(
        or_(
            Teacher.full_name.ilike(search_term),
            Teacher.email.ilike(search_term),
            Teacher.teacher_id.ilike(search_term),
            Teacher.phone_no.ilike(search_term)
        )
    ).all()

@router.get("/table/counsellors")
def search_counsellors_table(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    search_term = f"%{q}%"
    return db.query(Counsellor).filter(
        or_(
            Counsellor.full_name.ilike(search_term),
            Counsellor.email.ilike(search_term),
            Counsellor.counsellor_id.ilike(search_term),
            Counsellor.phone_no.ilike(search_term)
        )
    ).all()

@router.get("/table/courses")
def search_courses_table(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    search_term = f"%{q}%"
    return db.query(Course).filter(
        or_(
            Course.course_name.ilike(search_term),
            Course.course_code.ilike(search_term),
            Course.course_id.ilike(search_term)
        )
    ).all()


@router.get("/table/fees")
def search_fees_table(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    search_term = f"%{q}%"
    return db.query(Fee).outerjoin(Student, Fee.student_id == Student.student_id).filter(
        or_(
            Fee.fee_id.ilike(search_term),
            Fee.student_id.ilike(search_term),
            Fee.payment_mode.ilike(search_term),
            Fee.payment_status.ilike(search_term),
            Fee.cheque_no.ilike(search_term),
            Fee.dd_no.ilike(search_term),
            Student.full_name.ilike(search_term),
            cast(Fee.amount, String).ilike(search_term)
        )
    ).all()

@router.get("/table/salaries")
def search_salaries_table(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    search_term = f"%{q}%"
    return db.query(Salary).outerjoin(Teacher, Salary.teacher_id == Teacher.teacher_id).filter(
        or_(
            Salary.salary_id.ilike(search_term),
            Salary.teacher_id.ilike(search_term),
            Salary.payment_mode.ilike(search_term),
            Salary.transaction_id.ilike(search_term),
            Salary.status.ilike(search_term),
            Teacher.full_name.ilike(search_term),
            cast(Salary.total_salary, String).ilike(search_term),
            cast(Salary.fixed_salary, String).ilike(search_term)
        )
    ).all()

@router.get("/table/payouts")
def search_payouts_table(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    search_term = f"%{q}%"
    return db.query(Payout).outerjoin(Counsellor, Payout.counsellor_id == Counsellor.counsellor_id).filter(
        or_(
            Payout.id.ilike(search_term),
            Payout.payout_no.ilike(search_term),
            Payout.counsellor_id.ilike(search_term),
            Payout.payment_method.ilike(search_term),
            Payout.reference_no.ilike(search_term),
            Payout.status.ilike(search_term),
            Counsellor.full_name.ilike(search_term),
            cast(Payout.amount, String).ilike(search_term)
        )
    ).all()

@router.get("/table/announcements")
def search_announcements_table(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    search_term = f"%{q}%"
    return db.query(Announcement).filter(
        or_(
            Announcement.headline.ilike(search_term),
            Announcement.description.ilike(search_term),
            Announcement.role.ilike(search_term)
        )
    ).all()

@router.get("/table/ads")
def search_ads_table(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    search_term = f"%{q}%"
    return db.query(Advertisement).filter(
        or_(
            Advertisement.headline.ilike(search_term),
            Advertisement.tagline.ilike(search_term)
        )
    ).all()

@router.get("/table/enquiries")
def search_enquiries_table(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    search_term = f"%{q}%"
    return db.query(AdmissionEnquiry).filter(
        or_(
            AdmissionEnquiry.enquiry_id.ilike(search_term),
            AdmissionEnquiry.student_name.ilike(search_term),
            AdmissionEnquiry.student_phn_no.ilike(search_term),
            AdmissionEnquiry.student_email.ilike(search_term),
            AdmissionEnquiry.status.ilike(search_term)
        )
    ).all()

@router.get("/table/help_center")
def search_help_center_table(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    search_term = f"%{q}%"
    return db.query(HelpCenter).filter(
        or_(
            HelpCenter.report_id.ilike(search_term),
            HelpCenter.name.ilike(search_term),
            HelpCenter.email.ilike(search_term),
            HelpCenter.phone_no.ilike(search_term),
            HelpCenter.problem_description.ilike(search_term),
            HelpCenter.status.ilike(search_term)
        )
    ).all()

