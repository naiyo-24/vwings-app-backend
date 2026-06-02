from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path
import os
from datetime import datetime
from fastapi.responses import FileResponse
from db import get_db
from models.salary.salary_models import Salary
from models.auth.teacher_models import Teacher
from services.salary_id_generator import generate_salary_id
from services.salary_pdf_generator import generate_salary_slip_pdf
from routes.notification.notification_routes import create_notification

class SalaryCalculationRequest(BaseModel):
    teacher_id: str
    month: int
    year: int
    fixed_salary: float
    commission_per_student: float
    referrals_admitted: int
    transaction_id: str

router = APIRouter(prefix="/api/salaries", tags=["Salaries"])


# Create/upload salary file for a teacher
@router.post("/create", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_salary(
	teacher_id: str = Form(...),
	month: int = Form(...),
	year: int = Form(...),
	file: UploadFile = File(...),
	db: Session = Depends(get_db),
):
	# verify teacher exists
	teacher = db.query(Teacher).filter_by(teacher_id=teacher_id).first()
	if not teacher:
		raise HTTPException(status_code=404, detail="Teacher not found")

	now = datetime.utcnow()
	salary_id = generate_salary_id(now)

	# save file
	uploads_dir = Path("uploads") / "salaries" / salary_id
	uploads_dir.mkdir(parents=True, exist_ok=True)
	filename = f"{salary_id}_{file.filename}"
	file_path = uploads_dir / filename
	with open(file_path, "wb") as f:
		content = await file.read()
		f.write(content)

	db_salary = Salary(
		salary_id=salary_id,
		teacher_id=teacher_id,
		month=month,
		year=year,
		file_path=str(file_path),
		created_at=now,
		updated_at=now,
	)
	db.add(db_salary)
	db.commit()
	db.refresh(db_salary)

	return {"detail": "Salary uploaded", "salary_id": salary_id}

@router.post("/calculate-and-pay", response_model=dict, status_code=status.HTTP_201_CREATED)
async def calculate_and_pay_salary(
    request: SalaryCalculationRequest = Body(...),
    db: Session = Depends(get_db)
):
    teacher = db.query(Teacher).filter_by(teacher_id=request.teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
        
    now = datetime.utcnow()
    salary_id = generate_salary_id(now)
    
    total_commission = request.referrals_admitted * request.commission_per_student
    total_salary = request.fixed_salary + total_commission
    
    # generate pdf
    uploads_dir = Path("uploads") / "salaries" / salary_id
    uploads_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{salary_id}_salary_slip.pdf"
    file_path = uploads_dir / filename
    
    salary_data = {
        'teacher_name': teacher.full_name,
        'teacher_id': teacher.teacher_id,
        'month': request.month,
        'year': request.year,
        'fixed_salary': request.fixed_salary,
        'referrals_admitted': request.referrals_admitted,
        'commission_per_student': request.commission_per_student,
        'total_salary': total_salary,
        'transaction_id': request.transaction_id,
        'payment_mode': 'NEFT'
    }
    
    generate_salary_slip_pdf(salary_data, str(file_path))
    
    db_salary = Salary(
        salary_id=salary_id,
        teacher_id=request.teacher_id,
        month=request.month,
        year=request.year,
        fixed_salary=request.fixed_salary,
        commission_per_student=request.commission_per_student,
        referrals_admitted=request.referrals_admitted,
        total_salary=total_salary,
        payment_mode='NEFT',
        transaction_id=request.transaction_id,
        status='Paid',
        file_path=str(file_path),
        created_at=now,
        updated_at=now,
    )
    db.add(db_salary)
    db.commit()
    db.refresh(db_salary)
    
    # Notify Admin and Teacher
    create_notification(
        "Salary Disbursed",
        f"A salary of Rs. {total_salary} was successfully processed for {teacher.full_name}.",
        "admin"
    )
    create_notification(
        "Salary Received! 💰",
        f"A salary of Rs. {total_salary} has been disbursed to your account.",
        "teacher",
        request.teacher_id
    )
    
    return {"detail": "Salary calculated and paid successfully", "salary_id": salary_id}


# Get salary by id
@router.get("/get-by/{salary_id}", response_model=dict)
def get_salary_by_id(salary_id: str, db: Session = Depends(get_db)):
	salary = db.query(Salary).filter_by(salary_id=salary_id).first()
	if not salary:
		raise HTTPException(status_code=404, detail="Salary not found")
	return {
		"salary_id": salary.salary_id,
		"teacher_id": salary.teacher_id,
		"month": salary.month,
		"year": salary.year,
		"fixed_salary": getattr(salary, "fixed_salary", 0.0),
		"commission_per_student": getattr(salary, "commission_per_student", 0.0),
		"referrals_admitted": getattr(salary, "referrals_admitted", 0),
		"total_salary": getattr(salary, "total_salary", 0.0),
		"payment_mode": getattr(salary, "payment_mode", "NEFT"),
		"transaction_id": getattr(salary, "transaction_id", None),
		"status": getattr(salary, "status", "Paid"),
		"file_path": salary.file_path,
		"created_at": salary.created_at,
		"updated_at": salary.updated_at,
	}


# Get all salaries
@router.get("/get-all", response_model=List[dict])
def get_all_salaries(db: Session = Depends(get_db)):
	salaries = db.query(Salary).all()
	return [
		{
			"salary_id": s.salary_id,
			"teacher_id": s.teacher_id,
			"month": s.month,
			"year": s.year,
			"fixed_salary": getattr(s, "fixed_salary", 0.0),
			"commission_per_student": getattr(s, "commission_per_student", 0.0),
			"referrals_admitted": getattr(s, "referrals_admitted", 0),
			"total_salary": getattr(s, "total_salary", 0.0),
			"payment_mode": getattr(s, "payment_mode", "NEFT"),
			"transaction_id": getattr(s, "transaction_id", None),
			"status": getattr(s, "status", "Paid"),
			"file_path": s.file_path,
			"created_at": s.created_at,
			"updated_at": s.updated_at,
		}
		for s in salaries
	]


# Get salaries by teacher id
@router.get("/get-by-teacher/{teacher_id}", response_model=List[dict])
def get_salaries_by_teacher(teacher_id: str, db: Session = Depends(get_db)):
	salaries = db.query(Salary).filter_by(teacher_id=teacher_id).all()
	return [
		{
			"salary_id": s.salary_id,
			"teacher_id": s.teacher_id,
			"month": s.month,
			"year": s.year,
			"fixed_salary": getattr(s, "fixed_salary", 0.0),
			"commission_per_student": getattr(s, "commission_per_student", 0.0),
			"referrals_admitted": getattr(s, "referrals_admitted", 0),
			"total_salary": getattr(s, "total_salary", 0.0),
			"payment_mode": getattr(s, "payment_mode", "NEFT"),
			"transaction_id": getattr(s, "transaction_id", None),
			"status": getattr(s, "status", "Paid"),
			"file_path": s.file_path,
			"created_at": s.created_at,
			"updated_at": s.updated_at,
		}
		for s in salaries
	]


# Download salary PDF by teacher id, month, and year
@router.get("/download/{teacher_id}/{month}/{year}")
def download_salary(teacher_id: str, month: int, year: int, db: Session = Depends(get_db)):
	# Verify teacher exists
	teacher = db.query(Teacher).filter_by(teacher_id=teacher_id).first()
	if not teacher:
		raise HTTPException(status_code=404, detail="Teacher not found")

	# Get the salary record
	salary = db.query(Salary).filter_by(teacher_id=teacher_id, month=month, year=year).first()
	if not salary:
		raise HTTPException(status_code=404, detail="Salary not found for this month and year")

	# Check if file exists
	if not os.path.exists(salary.file_path):
		raise HTTPException(status_code=404, detail="Salary file not found")

	# Return the file
	return FileResponse(path=salary.file_path, filename=f"salary_{teacher_id}_{month}_{year}.pdf", media_type='application/pdf')


# Delete salary by id
@router.delete("/delete-by/{salary_id}", response_model=dict)
def delete_salary(salary_id: str, db: Session = Depends(get_db)):
	salary = db.query(Salary).filter_by(salary_id=salary_id).first()
	if not salary:
		raise HTTPException(status_code=404, detail="Salary not found")

	# remove file if exists
	try:
		if salary.file_path and os.path.exists(salary.file_path):
			os.remove(salary.file_path)
	except Exception:
		pass

	db.delete(salary)
	db.commit()
	return {"detail": "Salary deleted"}

