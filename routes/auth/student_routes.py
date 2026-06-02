from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import os
from pathlib import Path
import shutil
from datetime import datetime
from db import get_db
from models.auth.student_models import Student
from models.courses.course_models import Course
from models.fees.fees_models import Fee, StudentFeeProfile
from services.student_id_generator import generate_student_id
from services.fees_id_generator import generate_fee_id
from pydantic import BaseModel, EmailStr, Field
from routes.fees.fees_routes import generate_pdf_receipt
from routes.notification.notification_routes import create_notification

router = APIRouter(
	prefix="/api/students",
	tags=["Students"]
)

# Pydantic Schemas
class StudentBase(BaseModel):
	full_name: str
	phone_no: str
	email: EmailStr
	address: str
	guardian_name: str
	guardian_mobile_no: str
	guardian_email: Optional[EmailStr] = None
	course_availing: str
	interests: Optional[List[str]] = None
	hobbies: Optional[List[str]] = None
	profile_photo: Optional[str] = None

class StudentCreate(StudentBase):
	password: str

class StudentUpdate(BaseModel):
	full_name: Optional[str] = None
	phone_no: Optional[str] = None
	email: Optional[EmailStr] = None
	address: Optional[str] = None
	guardian_name: Optional[str] = None
	guardian_mobile_no: Optional[str] = None
	guardian_email: Optional[EmailStr] = None
	course_availing: Optional[str] = None
	interests: Optional[List[str]] = None
	hobbies: Optional[List[str]] = None
	password: Optional[str] = None
	profile_photo: Optional[str] = None

class LoginRequest(BaseModel):
	email: EmailStr
	password: str

class StudentOut(StudentBase):
	student_id: str
	created_at: datetime
	updated_at: datetime
	course_name: Optional[str] = None
	counsellor_id: Optional[str] = None

	class Config:
		from_attributes = True

# Create Student with profile photo upload
@router.post("/create", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
async def create_student(
	full_name: str = Form(...),
	phone_no: str = Form(...),
	email: EmailStr = Form(...),
	address: str = Form(...),
	guardian_name: str = Form(...),
	guardian_mobile_no: str = Form(...),
	guardian_email: Optional[EmailStr] = Form(None),
	course_availing: str = Form(...),
	interests: Optional[str] = Form(None),  # JSON string
	hobbies: Optional[str] = Form(None),    # JSON string
	password: str = Form(...),
	payment_mode: Optional[str] = Form("online"),
	payment_plan: Optional[str] = Form("full"),
	amount_paid: Optional[float] = Form(0.0),
	cheque_no: Optional[str] = Form(None),
	dd_no: Optional[str] = Form(None),
	profile_photo: Optional[UploadFile] = File(None),
	db: Session = Depends(get_db)
):
	import json
	# Check required fields
	required_fields = [full_name, email, phone_no, guardian_name, guardian_mobile_no, password, address, course_availing]
	if not all(required_fields):
		raise HTTPException(status_code=400, detail="Missing required fields.")
	# Check if email already exists
	if db.query(Student).filter_by(email=email).first():
		raise HTTPException(status_code=409, detail="Email already registered.")
	# Check if course exists
	course = db.query(Course).filter_by(course_id=course_availing).first()
	if not course:
		raise HTTPException(status_code=404, detail="Course not found.")
	now = datetime.utcnow()
	student_id = generate_student_id(now)
	# Handle profile photo upload
	profile_photo_path = None
	if profile_photo:
		uploads_dir = Path("uploads") / "students" / student_id
		uploads_dir.mkdir(parents=True, exist_ok=True)
		file_ext = os.path.splitext(profile_photo.filename)[1]
		file_name = f"profile{file_ext}"
		file_path = uploads_dir / file_name
		with open(file_path, "wb") as buffer:
			shutil.copyfileobj(profile_photo.file, buffer)
		# Always use relative path from project root
		profile_photo_path = os.path.relpath(str(file_path), os.getcwd())
	# Parse JSON fields
	interests_list = json.loads(interests) if interests else None
	hobbies_list = json.loads(hobbies) if hobbies else None
	db_student = Student(
		student_id=student_id,
		full_name=full_name,
		phone_no=phone_no,
		email=email,
		address=address,
		guardian_name=guardian_name,
		guardian_mobile_no=guardian_mobile_no,
		guardian_email=guardian_email,
		course_availing=course_availing,
		interests=interests_list,
		hobbies=hobbies_list,
		password=password,
		profile_photo=profile_photo_path,
		created_at=now,
		updated_at=now
	)
	db.add(db_student)
	
	# Handle Onboarding Fee Profile & Cash Payment
	course_fee = 0.0
	if course.general_data and "course_fees" in course.general_data:
		course_fee = float(course.general_data["course_fees"])
		
	fee_profile = StudentFeeProfile(
		student_id=student_id,
		total_fee=course_fee,
		payment_plan=payment_plan,
		created_at=now,
		updated_at=now
	)
	db.add(fee_profile)
	
	if payment_mode.lower() in ["cash", "cheque", "demand_draft"] and amount_paid > 0:
		txn_prefix = "CASH"
		if payment_mode.lower() == "cheque":
			txn_prefix = "CHEQUE"
		elif payment_mode.lower() == "demand_draft":
			txn_prefix = "DD"
		cash_txn_id = f"{txn_prefix}_{int(now.timestamp())}"
		fee_id = generate_fee_id(now)
		cash_fee = Fee(
			fee_id=fee_id,
			student_id=student_id,
			installment_no=1 if payment_plan == "installment" else 0,
			payment_type=payment_plan,
			payment_mode=payment_mode.lower(),
			cheque_no=cheque_no,
			dd_no=dd_no,
			amount=amount_paid,
			payment_status="completed",
			razorpay_payment_id=cash_txn_id,
			created_at=now,
			updated_at=now
		)
		db.add(cash_fee)
		db.commit()
		db.refresh(cash_fee)
		receipt_path = generate_pdf_receipt(cash_fee, db_student, course)
		cash_fee.file_path = receipt_path

	db.commit()
	db.refresh(db_student)
	
	# Notify the student
	create_notification(
		"Welcome to VWings24x7! 🎉",
		f"Hi {full_name}, your account has been successfully created. Welcome aboard!",
		"student",
		student_id
	)
	
	# Notify the admins
	create_notification(
		"New Student Onboarded",
		f"{full_name} has been successfully registered to '{course.course_name}'.",
		"admin"
	)

	return StudentOut(
		**db_student.__dict__,
		course_name=course.course_name
	)

# Login student
@router.post("/login", response_model=StudentOut)
def login_student(request: LoginRequest, db: Session = Depends(get_db)):
	student = db.query(Student).filter_by(email=request.email).first()
	if not student or student.password != request.password:
		raise HTTPException(status_code=401, detail="Invalid credentials.")
	course = db.query(Course).filter_by(course_id=student.course_availing).first()
	course_name = course.course_name if course else None
	profile_photo_path = None
	if student.profile_photo:
		try:
			profile_photo_path = os.path.relpath(str(Path(student.profile_photo)), os.getcwd())
		except Exception:
			profile_photo_path = student.profile_photo
	return StudentOut(**{**student.__dict__, "profile_photo": profile_photo_path}, course_name=course_name)

# Get all students
@router.get("/get-all", response_model=List[StudentOut])
def get_all_students(db: Session = Depends(get_db)):
	students = db.query(Student).all()
	result = []
	for s in students:
		course = db.query(Course).filter_by(course_id=s.course_availing).first()
		course_name = course.course_name if course else None
		# Always return relative path for profile_photo
		profile_photo_path = None
		if s.profile_photo:
			try:
				profile_photo_path = os.path.relpath(str(Path(s.profile_photo)), os.getcwd())
			except Exception:
				profile_photo_path = s.profile_photo
				
		from models.admission.admission_enquiry_models import AdmissionEnquiry
		enquiry = db.query(AdmissionEnquiry).filter((AdmissionEnquiry.student_email == s.email) | (AdmissionEnquiry.student_phn_no == s.phone_no), AdmissionEnquiry.status == "converted").first()
		counsellor_id = enquiry.counsellor_id if enquiry else None

		result.append(StudentOut(**{**s.__dict__, "profile_photo": profile_photo_path}, course_name=course_name, counsellor_id=counsellor_id))
	return result

# Get student by ID
@router.get("/get-by/{student_id}", response_model=StudentOut)
def get_student_by_id(student_id: str, db: Session = Depends(get_db)):
	student = db.query(Student).filter_by(student_id=student_id).first()
	if not student:
		raise HTTPException(status_code=404, detail="Student not found.")
	course = db.query(Course).filter_by(course_id=student.course_availing).first()
	course_name = course.course_name if course else None
	profile_photo_path = None
	if student.profile_photo:
		try:
			profile_photo_path = os.path.relpath(str(Path(student.profile_photo)), os.getcwd())
		except Exception:
			profile_photo_path = student.profile_photo
	return StudentOut(**{**student.__dict__, "profile_photo": profile_photo_path}, course_name=course_name)

# Update each parameter by ID, including profile photo
@router.put("/put-by/{student_id}", response_model=StudentOut)
async def update_student(
	student_id: str,
	full_name: Optional[str] = Form(None),
	phone_no: Optional[str] = Form(None),
	email: Optional[EmailStr] = Form(None),
	address: Optional[str] = Form(None),
	guardian_name: Optional[str] = Form(None),
	guardian_mobile_no: Optional[str] = Form(None),
	guardian_email: Optional[EmailStr] = Form(None),
	course_availing: Optional[str] = Form(None),
	interests: Optional[str] = Form(None),
	hobbies: Optional[str] = Form(None),
	password: Optional[str] = Form(None),
	profile_photo: Optional[UploadFile] = File(None),
	db: Session = Depends(get_db)
):
	import json
	student = db.query(Student).filter_by(student_id=student_id).first()
	if not student:
		raise HTTPException(status_code=404, detail="Student not found.")
	update_data = {}
	if full_name is not None:
		update_data["full_name"] = full_name
	if phone_no is not None:
		update_data["phone_no"] = phone_no
	if email is not None:
		update_data["email"] = email
	if address is not None:
		update_data["address"] = address
	if guardian_name is not None:
		update_data["guardian_name"] = guardian_name
	if guardian_mobile_no is not None:
		update_data["guardian_mobile_no"] = guardian_mobile_no
	if guardian_email is not None:
		update_data["guardian_email"] = guardian_email
	if course_availing is not None:
		# Validate course
		course = db.query(Course).filter_by(course_id=course_availing).first()
		if not course:
			raise HTTPException(status_code=404, detail="Course not found.")
		update_data["course_availing"] = course_availing
	if interests is not None:
		if interests == "":
			update_data["interests"] = None
		else:
			try:
				update_data["interests"] = json.loads(interests)
			except Exception:
				raise HTTPException(status_code=400, detail="Invalid JSON for interests")
	if hobbies is not None:
		if hobbies == "":
			update_data["hobbies"] = None
		else:
			try:
				update_data["hobbies"] = json.loads(hobbies)
			except Exception:
				raise HTTPException(status_code=400, detail="Invalid JSON for hobbies")
	if password is not None:
		update_data["password"] = password
		# Handle profile photo update
		if profile_photo:
			uploads_dir = Path("uploads") / "students" / student_id
			uploads_dir.mkdir(parents=True, exist_ok=True)
			file_ext = os.path.splitext(profile_photo.filename)[1]
			file_name = f"profile{file_ext}"
			file_path = uploads_dir / file_name
			with open(file_path, "wb") as buffer:
				shutil.copyfileobj(profile_photo.file, buffer)
			# Use os.path.relpath for robust relative path
			profile_photo_path = os.path.relpath(str(file_path), os.getcwd())
			update_data["profile_photo"] = profile_photo_path
	for key, value in update_data.items():
		setattr(student, key, value)
	student.updated_at = datetime.utcnow()
	db.commit()
	db.refresh(student)
	course = db.query(Course).filter_by(course_id=student.course_availing).first()
	course_name = course.course_name if course else None
	return StudentOut(**student.__dict__, course_name=course_name)

# Delete student by ID
@router.delete("/delete-by/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(student_id: str, db: Session = Depends(get_db)):
	student = db.query(Student).filter_by(student_id=student_id).first()
	if not student:
		raise HTTPException(status_code=404, detail="Student not found.")
	db.delete(student)
	db.commit()
	return

# Bulk delete students
class BulkDeleteRequest(BaseModel):
	student_ids: List[str] = Field(..., example=["STUDENT123", "STUDENT456"])

@router.delete("/bulk/delete", status_code=status.HTTP_204_NO_CONTENT)
def bulk_delete_students(request: BulkDeleteRequest, db: Session = Depends(get_db)):
	students = db.query(Student).filter(Student.student_id.in_(request.student_ids)).all()
	if not students:
		raise HTTPException(status_code=404, detail="No students found for given IDs.")
	for student in students:
		db.delete(student)
	db.commit()
	return
