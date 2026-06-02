from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from pathlib import Path
import os
import shutil
import json
from db import get_db
from models.auth.teacher_models import Teacher
from models.courses.course_models import Course
from services.teacher_id_generator import generate_teacher_id
from pydantic import BaseModel, EmailStr
from datetime import datetime
from routes.notification.notification_routes import create_notification

router = APIRouter(prefix="/api/teachers", tags=["Teachers"])


# Helper: fetch course details for a list of course_ids
def get_course_details(db: Session, course_ids: List[str]):
	if not course_ids:
		return []
	courses = db.query(Course).filter(Course.course_id.in_(course_ids)).all()
	return [{"course_id": c.course_id, "course_name": c.course_name} for c in courses]


# Pydantic Schemas
class TeacherBase(BaseModel):
	full_name: str
	phone_no: str
	email: EmailStr
	alternative_phone_no: Optional[str] = None
	address: Optional[str] = None
	qualification: Optional[str] = None
	experience: Optional[str] = None
	courses_assigned: Optional[List[Dict[str, str]]] = None
	profile_photo: Optional[str] = None
	bank_account_no: Optional[str] = None
	bank_account_name: Optional[str] = None
	bank_branch_name: Optional[str] = None
	ifsc_code: Optional[str] = None
	upiid: Optional[str] = None
	monthly_salary: Optional[float] = None


class TeacherCreate(TeacherBase):
	password: str


class TeacherUpdate(BaseModel):
	full_name: Optional[str] = None
	phone_no: Optional[str] = None
	email: Optional[EmailStr] = None
	alternative_phone_no: Optional[str] = None
	address: Optional[str] = None
	qualification: Optional[str] = None
	experience: Optional[str] = None
	courses_assigned: Optional[List[str]] = None
	bank_account_no: Optional[str] = None
	bank_account_name: Optional[str] = None
	bank_branch_name: Optional[str] = None
	ifsc_code: Optional[str] = None
	upiid: Optional[str] = None
	monthly_salary: Optional[float] = None
	password: Optional[str] = None
	profile_photo: Optional[str] = None


class TeacherOut(TeacherBase):
	teacher_id: str
	created_at: datetime
	updated_at: datetime

	class Config:
		from_attributes = True


# Login schemas
class TeacherLogin(BaseModel):
	email: EmailStr
	password: str


class TeacherLoginResponse(BaseModel):
	message: str
	teacher: TeacherOut

	class Config:
		from_attributes = True


# Create Teacher
@router.post("/create", response_model=TeacherOut, status_code=status.HTTP_201_CREATED)
async def create_teacher(
	full_name: str = Form(...),
	phone_no: str = Form(...),
	email: EmailStr = Form(...),
	alternative_phone_no: Optional[str] = Form(None),
	address: Optional[str] = Form(None),
	qualification: Optional[str] = Form(None),
	experience: Optional[str] = Form(None),
	courses_assigned: Optional[str] = Form(None),  # JSON string list of course_ids
	bank_account_no: Optional[str] = Form(None),
	bank_account_name: Optional[str] = Form(None),
	bank_branch_name: Optional[str] = Form(None),
	ifsc_code: Optional[str] = Form(None),
	upiid: Optional[str] = Form(None),
	monthly_salary: Optional[float] = Form(None),
	password: str = Form(...),
	profile_photo: Optional[UploadFile] = File(None),
	db: Session = Depends(get_db),
):
	# basic validations
	if db.query(Teacher).filter_by(email=email).first():
		raise HTTPException(status_code=409, detail="Email already registered.")
	if db.query(Teacher).filter_by(phone_no=phone_no).first():
		raise HTTPException(status_code=409, detail="Phone number already registered.")

	now = datetime.utcnow()
	teacher_id = generate_teacher_id(now)

	# parse courses_assigned
	course_list = []
	if courses_assigned:
		try:
			course_ids = json.loads(courses_assigned)
		except Exception:
			raise HTTPException(status_code=400, detail="Invalid courses_assigned format. Should be JSON list of course_ids.")
		course_list = get_course_details(db, course_ids)

	# handle profile photo
	profile_photo_path = None
	if profile_photo:
		uploads_dir = Path("uploads") / "teacher" / teacher_id
		uploads_dir.mkdir(parents=True, exist_ok=True)
		file_ext = os.path.splitext(profile_photo.filename)[1]
		file_name = f"profile{file_ext}"
		file_path = uploads_dir / file_name
		with open(file_path, "wb") as buffer:
			shutil.copyfileobj(profile_photo.file, buffer)
		profile_photo_path = os.path.relpath(str(file_path), os.getcwd())

	db_teacher = Teacher(
		teacher_id=teacher_id,
		full_name=full_name,
		phone_no=phone_no,
		email=email,
		alternative_phone_no=alternative_phone_no,
		address=address,
		qualification=qualification,
		experience=experience,
		courses_assigned=course_list,
		bank_account_no=bank_account_no,
		bank_account_name=bank_account_name,
		bank_branch_name=bank_branch_name,
		ifsc_code=ifsc_code,
		upiid=upiid,
		monthly_salary=monthly_salary,
		password=password,
		profile_photo=profile_photo_path,
		created_at=now,
		updated_at=now,
	)
	db.add(db_teacher)
	db.commit()
	db.refresh(db_teacher)

	# Notify Teacher and Admin
	create_notification(
		"Welcome to VWings24x7! 🎉",
		f"Hi {full_name}, your teacher account has been successfully created.",
		"teacher",
		teacher_id
	)
	create_notification(
		"New Faculty Onboarded",
		f"{full_name} has been added as a Teacher.",
		"admin"
	)

	# return using same pattern as student_routes
	return TeacherOut(**{**db_teacher.__dict__})


# Login endpoint
@router.post("/login", response_model=TeacherLoginResponse)
def login_teacher(credentials: TeacherLogin, db: Session = Depends(get_db)):
	teacher = db.query(Teacher).filter(Teacher.email == credentials.email).first()
	if not teacher:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
	# plaintext password check (replace with hashed check in production)
	if credentials.password != teacher.password:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
	return {"message": "Login successful", "teacher": teacher}


# Get all teachers
@router.get("/get-all", response_model=List[TeacherOut])
def get_all_teachers(db: Session = Depends(get_db)):
	teachers = db.query(Teacher).all()
	result = []
	for t in teachers:
		# ensure courses_assigned names are up-to-date
		if t.courses_assigned:
			course_ids = [c["course_id"] for c in t.courses_assigned]
			t.courses_assigned = get_course_details(db, course_ids)
		# normalize profile_photo to relative path
		profile_photo_path = None
		if t.profile_photo:
			try:
				profile_photo_path = os.path.relpath(str(Path(t.profile_photo)), os.getcwd())
			except Exception:
				profile_photo_path = t.profile_photo
		result.append(TeacherOut(**{**t.__dict__, "profile_photo": profile_photo_path}))
	return result


# Get teacher by id
@router.get("/get-by/{teacher_id}", response_model=TeacherOut)
def get_teacher_by_id(teacher_id: str, db: Session = Depends(get_db)):
	teacher = db.query(Teacher).filter_by(teacher_id=teacher_id).first()
	if not teacher:
		raise HTTPException(status_code=404, detail="Teacher not found")
	if teacher.courses_assigned:
		course_ids = [c["course_id"] for c in teacher.courses_assigned]
		teacher.courses_assigned = get_course_details(db, course_ids)
	profile_photo_path = None
	if teacher.profile_photo:
		try:
			profile_photo_path = os.path.relpath(str(Path(teacher.profile_photo)), os.getcwd())
		except Exception:
			profile_photo_path = teacher.profile_photo
	return TeacherOut(**{**teacher.__dict__, "profile_photo": profile_photo_path})


# Update teacher by id
@router.put("/put-by/{teacher_id}", response_model=TeacherOut)
async def update_teacher(
	teacher_id: str,
	full_name: Optional[str] = Form(None),
	phone_no: Optional[str] = Form(None),
	email: Optional[EmailStr] = Form(None),
	alternative_phone_no: Optional[str] = Form(None),
	address: Optional[str] = Form(None),
	qualification: Optional[str] = Form(None),
	experience: Optional[str] = Form(None),
	courses_assigned: Optional[str] = Form(None),  # JSON string list
	bank_account_no: Optional[str] = Form(None),
	bank_account_name: Optional[str] = Form(None),
	bank_branch_name: Optional[str] = Form(None),
	ifsc_code: Optional[str] = Form(None),
	upiid: Optional[str] = Form(None),
	monthly_salary: Optional[float] = Form(None),
	password: Optional[str] = Form(None),
	profile_photo: Optional[UploadFile] = File(None),
	db: Session = Depends(get_db),
):
	teacher = db.query(Teacher).filter_by(teacher_id=teacher_id).first()
	if not teacher:
		raise HTTPException(status_code=404, detail="Teacher not found")

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
	if bank_branch_name is not None:
		update_data["bank_branch_name"] = bank_branch_name
	if ifsc_code is not None:
		update_data["ifsc_code"] = ifsc_code
	if upiid is not None:
		update_data["upiid"] = upiid
	if monthly_salary is not None:
		update_data["monthly_salary"] = monthly_salary
	if password is not None:
		update_data["password"] = password

	if courses_assigned is not None:
		try:
			course_ids = json.loads(courses_assigned)
		except Exception:
			raise HTTPException(status_code=400, detail="Invalid courses_assigned format. Should be JSON list of course_ids.")
		update_data["courses_assigned"] = get_course_details(db, course_ids)

	# apply updates
	for k, v in update_data.items():
		setattr(teacher, k, v)

	# handle profile photo
	if profile_photo:
		uploads_dir = Path("uploads") / "teacher" / teacher_id
		uploads_dir.mkdir(parents=True, exist_ok=True)
		file_ext = os.path.splitext(profile_photo.filename)[1]
		file_name = f"profile{file_ext}"
		file_path = uploads_dir / file_name
		with open(file_path, "wb") as buffer:
			shutil.copyfileobj(profile_photo.file, buffer)
		teacher.profile_photo = os.path.relpath(str(file_path), os.getcwd())

	teacher.updated_at = datetime.utcnow()
	db.commit()
	db.refresh(teacher)

	profile_photo_path = None
	if teacher.profile_photo:
		try:
			profile_photo_path = os.path.relpath(str(Path(teacher.profile_photo)), os.getcwd())
		except Exception:
			profile_photo_path = teacher.profile_photo

	return TeacherOut(**{**teacher.__dict__, "profile_photo": profile_photo_path})


# Delete by id
@router.delete("/delete-by/{teacher_id}", response_model=dict)
def delete_teacher(teacher_id: str, db: Session = Depends(get_db)):
	teacher = db.query(Teacher).filter_by(teacher_id=teacher_id).first()
	if not teacher:
		raise HTTPException(status_code=404, detail="Teacher not found")
	db.delete(teacher)
	db.commit()
	return {"detail": "Teacher deleted"}


# Bulk delete (query params: ids=ID1&ids=ID2)
@router.delete("/bulk-delete", response_model=dict)
def bulk_delete_teachers(ids: List[str] = Query(...), db: Session = Depends(get_db)):
	teachers = db.query(Teacher).filter(Teacher.teacher_id.in_(ids)).all()
	for t in teachers:
		db.delete(t)
	db.commit()
	return {"detail": f"Deleted {len(teachers)} teachers"}

