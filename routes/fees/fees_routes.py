from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path
import os
import json
import razorpay
from datetime import datetime, timedelta
from fastapi.responses import FileResponse
from pydantic import BaseModel
from db import get_db
from models.fees.fees_models import Fee, StudentFeeProfile
from models.auth.student_models import Student
from models.courses.course_models import Course
from services.fees_id_generator import generate_fee_id
from services.commission_service import process_commission
from routes.notification.notification_routes import create_notification


from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

router = APIRouter(prefix="/api/fees", tags=["Fees"])

# Razorpay client setup
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_dummy_key")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "dummy_secret")
rzp_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

class CreateOrderRequest(BaseModel):
    student_id: str
    payment_type: str  # 'full' or 'installment'
    installment_no: Optional[int] = None
    amount: int  # Amount in rupees

class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    fee_id: str

class CashPaymentRequest(BaseModel):
    student_id: str
    payment_type: str
    installment_no: Optional[int] = None
    amount: float
    payment_mode: Optional[str] = "cash"
    cheque_no: Optional[str] = None
    dd_no: Optional[str] = None

class UpdateFeeRequest(BaseModel):
    amount: int
    payment_status: str
    payment_type: str
    installment_no: Optional[int] = None

class FeeProfileRequest(BaseModel):
    student_id: str
    total_fee: float
    payment_plan: str # "full" or "installment"

@router.post("/profile", response_model=dict)
async def update_fee_profile(request: FeeProfileRequest, db: Session = Depends(get_db)):
    student = db.query(Student).filter_by(student_id=request.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    profile = db.query(StudentFeeProfile).filter_by(student_id=request.student_id).first()
    if not profile:
        profile = StudentFeeProfile(student_id=request.student_id)
        db.add(profile)
    
    profile.total_fee = request.total_fee
    profile.payment_plan = request.payment_plan
    db.commit()
    db.refresh(profile)
    return {"detail": "Fee profile updated", "profile": {"student_id": profile.student_id, "total_fee": profile.total_fee, "payment_plan": profile.payment_plan}}

@router.get("/profile/{student_id}", response_model=dict)
async def get_fee_profile(student_id: str, db: Session = Depends(get_db)):
    student = db.query(Student).filter_by(student_id=student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    profile = db.query(StudentFeeProfile).filter_by(student_id=student_id).first()
    all_fees = db.query(Fee).filter_by(student_id=student_id).all()
    completed_fees = [f for f in all_fees if f.payment_status == "completed"]
    total_paid = sum([f.amount or 0 for f in completed_fees])
    online_paid = sum([f.amount or 0 for f in completed_fees if not f.payment_mode or f.payment_mode.lower() == 'online'])
    cash_paid = sum([f.amount or 0 for f in completed_fees if f.payment_mode and f.payment_mode.lower() == 'cash'])


    # Determine which installments are already paid
    paid_installments = [f.installment_no for f in completed_fees if f.installment_no is not None]

    # Calculate default fee from course if profile doesn't exist
    total_fee = profile.total_fee if profile else 0.0
    payment_plan = profile.payment_plan if profile else "full"
    
    if not profile and student.course_availing:
        course = db.query(Course).filter_by(course_id=student.course_availing).first()
        if course and course.general_data:
            total_fee = float(course.general_data.get("course_fees", 0.0))

    # Calculate next required installment
    next_installment = None
    for i in range(1, 5): # 4 installments
        if i not in paid_installments:
            next_installment = i
            break

    return {
        "student_id": student_id,
        "total_fee": total_fee,
        "payment_plan": payment_plan,
        "total_paid": total_paid,
        "online_paid": online_paid,
        "cash_paid": cash_paid,
        "paid_installments": paid_installments,
        "next_installment": next_installment,
        "fees": [
            {
                "fee_id": f.fee_id,
                "amount": f.amount,
                "installment_no": f.installment_no,
                "payment_type": f.payment_type,
                "payment_mode": f.payment_mode,
                "payment_status": f.payment_status,
                "file_path": f.file_path,
                "created_at": f.created_at
            } for f in all_fees
        ]
    }

@router.post("/create-order")
def create_razorpay_order(request: CreateOrderRequest, db: Session = Depends(get_db)):
    student = db.query(Student).filter_by(student_id=request.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    amount_paise = request.amount * 100
    try:
        order_data = {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": f"receipt_{request.student_id}_{datetime.now().timestamp()}",
            "payment_capture": 1
        }
        order = rzp_client.order.create(data=order_data)

        # Create pending fee record
        fee_id = generate_fee_id(datetime.utcnow())
        db_fee = Fee(
            fee_id=fee_id,
            student_id=request.student_id,
            installment_no=request.installment_no if request.payment_type == 'installment' else 0,
            payment_type=request.payment_type,
            amount=request.amount,
            payment_status="pending",
            razorpay_order_id=order["id"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(db_fee)
        db.commit()

        return {
            "razorpay_order_id": order["id"], 
            "amount": amount_paise, 
            "currency": "INR", 
            "fee_id": fee_id,
            "key": RAZORPAY_KEY_ID
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def generate_pdf_receipt(fee: Fee, student: Student, course: Course):
    uploads_dir = Path("uploads") / "fees" / fee.fee_id
    uploads_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{fee.fee_id}_receipt.pdf"
    file_path = uploads_dir / filename
    
    doc = SimpleDocTemplate(str(file_path), pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle', parent=styles['Heading1'],
        alignment=TA_CENTER, fontSize=24, spaceAfter=5, textColor=colors.HexColor('#f59e0b')
    )
    
    # Header
    elements.append(Paragraph("<b>VWings24x7</b>", title_style))
    elements.append(Paragraph("<font size=14>Official Fee Receipt</font>", ParagraphStyle('SubTitle', alignment=TA_CENTER, spaceAfter=30)))
    
    # Convert UTC to IST (+5:30) for display
    display_time = fee.updated_at + timedelta(hours=5, minutes=30) if fee.updated_at else datetime.now()
    
    # Meta info (Date, Time, IDs)
    meta_data = [
        [Paragraph(f"<b>Receipt ID:</b> {fee.fee_id}"), Paragraph(f"<b>Date:</b> {display_time.strftime('%d-%b-%Y')}")],
        [Paragraph(f"<b>Transaction ID:</b> {fee.razorpay_payment_id}"), Paragraph(f"<b>Time:</b> {display_time.strftime('%I:%M %p')}")]
    ]
    meta_table = Table(meta_data, colWidths=[300, 200])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 20))
    
    # Details Table
    ptype = f"Installment #{fee.installment_no}" if fee.payment_type == 'installment' else 'Full Payment'
    
    table_data = [
        ['Description', 'Details'],
        ['Student Name', student.full_name if student else 'Unknown'],
        ['Student ID', student.student_id if student else 'Unknown'],
        ['Course Enrolled', course.course_name if course else 'N/A'],
        ['Payment Type', ptype],
        ['Payment Mode', fee.payment_mode.title() if hasattr(fee, 'payment_mode') and fee.payment_mode else 'Online Payment'],
        ['Status', 'SUCCESS'],
        ['Amount Paid', f"Rs. {fee.amount}"]
    ]
    
    details_table = Table(table_data, colWidths=[200, 330])
    details_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2937')), # Dark gray header
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9fafb')), # Light gray rows
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d1d5db')), # Borders
        ('PADDING', (0, 1), (-1, -1), 10),
    ]))
    
    elements.append(details_table)
    elements.append(Spacer(1, 40))
    
    # Footer
    elements.append(Paragraph("<i>Thank you for your payment!</i>", ParagraphStyle('Thanks', alignment=TA_CENTER, spaceAfter=10)))
    elements.append(Paragraph("<i>This is a computer-generated receipt and does not require a signature.</i>", ParagraphStyle('Footer', alignment=TA_CENTER, textColor=colors.gray)))
    
    doc.build(elements)
    
    return str(file_path).replace("\\", "/")


@router.post("/verify-payment")
def verify_payment(request: VerifyPaymentRequest, db: Session = Depends(get_db)):
    try:
        params_dict = {
            'razorpay_order_id': request.razorpay_order_id,
            'razorpay_payment_id': request.razorpay_payment_id,
            'razorpay_signature': request.razorpay_signature
        }
        rzp_client.utility.verify_payment_signature(params_dict)

        fee = db.query(Fee).filter_by(fee_id=request.fee_id).first()
        if not fee:
            raise HTTPException(status_code=404, detail="Fee record not found")

        fee.payment_status = "completed"
        fee.razorpay_payment_id = request.razorpay_payment_id
        fee.updated_at = datetime.utcnow()
        
        student = db.query(Student).filter_by(student_id=fee.student_id).first()
        course = db.query(Course).filter_by(course_id=student.course_availing).first() if student else None
        
        receipt_path = generate_pdf_receipt(fee, student, course)
        fee.file_path = receipt_path

        db.commit()
        
        # Process commission
        process_commission(fee, db)
        
        # Notifications
        create_notification(
            "Payment Successful", 
            f"We have received your payment of Rs. {fee.amount}.", 
            "student", 
            fee.student_id
        )
        create_notification(
            "New Online Payment", 
            f"Received Rs. {fee.amount} from {student.full_name} via Razorpay.", 
            "admin"
        )

        return {"status": "success", "message": "Payment verified successfully", "file_path": receipt_path}
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid payment signature")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/add-cash-payment")
def add_cash_payment(request: CashPaymentRequest, db: Session = Depends(get_db)):
    student = db.query(Student).filter_by(student_id=request.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    now = datetime.utcnow()
    fee_id = generate_fee_id(now)
    txn_prefix = "CASH"
    if request.payment_mode == "cheque":
        txn_prefix = "CHEQUE"
    elif request.payment_mode == "demand_draft":
        txn_prefix = "DD"
    cash_txn_id = f"{txn_prefix}_{now.strftime('%Y%m%d%H%M%S')}"

    db_fee = Fee(
        fee_id=fee_id,
        student_id=request.student_id,
        installment_no=request.installment_no if request.payment_type == 'installment' else 0,
        payment_type=request.payment_type,
        payment_mode=request.payment_mode,
        cheque_no=request.cheque_no,
        dd_no=request.dd_no,
        amount=int(request.amount),
        payment_status="completed",
        razorpay_order_id=cash_txn_id,
        razorpay_payment_id=cash_txn_id,
        created_at=now,
        updated_at=now
    )
    db.add(db_fee)
    db.commit()
    db.refresh(db_fee)

    course = db.query(Course).filter_by(course_id=student.course_availing).first() if student else None
    
    receipt_path = generate_pdf_receipt(db_fee, student, course)
    db_fee.file_path = receipt_path
    db.commit()
    
    # Process commission
    process_commission(db_fee, db)
    
    # Notifications
    create_notification(
        "Cash Payment Recorded", 
        f"Your offline payment of Rs. {db_fee.amount} has been successfully recorded.", 
        "student", 
        request.student_id
    )
    create_notification(
        "New Cash Payment", 
        f"Recorded Rs. {db_fee.amount} from {student.full_name} via {request.payment_mode}.", 
        "admin"
    )

    return {"status": "success", "message": "Cash payment added successfully", "fee_id": fee_id, "cash_txn_id": cash_txn_id, "file_path": receipt_path}

# Legacy manual fee upload
@router.post("/create", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_fee(
	student_id: str = Form(...),
	installment_no: int = Form(...),
	file: UploadFile = File(...),
	db: Session = Depends(get_db),
):
	student = db.query(Student).filter_by(student_id=student_id).first()
	if not student:
		raise HTTPException(status_code=404, detail="Student not found")

	now = datetime.utcnow()
	fee_id = generate_fee_id(now)
	uploads_dir = Path("uploads") / "fees" / fee_id
	uploads_dir.mkdir(parents=True, exist_ok=True)
	filename = f"{fee_id}_{file.filename}"
	file_path = uploads_dir / filename
	with open(file_path, "wb") as f:
		content = await file.read()
		f.write(content)

	db_fee = Fee(
		fee_id=fee_id,
		student_id=student_id,
		installment_no=installment_no,
		file_path=str(file_path),
        payment_type="offline",
        payment_status="completed",
		created_at=now,
		updated_at=now,
	)
	db.add(db_fee)
	db.commit()
	db.refresh(db_fee)

	# Process commission
	process_commission(db_fee, db)

	return {"detail": "Fee uploaded", "fee_id": fee_id}

# Get fee by id
@router.get("/get-by/{fee_id}", response_model=dict)
def get_fee_by_id(fee_id: str, db: Session = Depends(get_db)):
    fee = db.query(Fee).filter_by(fee_id=fee_id).first()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")
    return {
		"fee_id": fee.fee_id,
		"student_id": fee.student_id,
		"installment_no": fee.installment_no,
		"file_path": fee.file_path,
        "payment_type": fee.payment_type,
        "amount": fee.amount,
        "payment_status": fee.payment_status,
		"created_at": fee.created_at,
		"updated_at": fee.updated_at,
    }

# Get all fees
@router.get("/get-all", response_model=List[dict])
def get_all_fees(db: Session = Depends(get_db)):
    fees = db.query(Fee).all()
    return [
        {
            "fee_id": f.fee_id,
            "student_id": f.student_id,
            "payment_type": f.payment_type,
            "installment_no": f.installment_no,
            "amount": f.amount,
            "payment_status": f.payment_status,
            "payment_mode": f.payment_mode,
            "razorpay_payment_id": f.razorpay_payment_id,
            "cheque_no": f.cheque_no,
            "dd_no": f.dd_no,
            "file_path": f.file_path,
            "created_at": f.created_at,
        }
        for f in fees
    ]

# Get fees by student id
@router.get("/get-by-student/{student_id}", response_model=List[dict])
def get_fees_by_student(student_id: str, db: Session = Depends(get_db)):
    fees = db.query(Fee).filter_by(student_id=student_id).all()
    return [
        {
            "fee_id": f.fee_id,
            "student_id": f.student_id,
            "payment_type": f.payment_type,
            "installment_no": f.installment_no,
            "amount": f.amount,
            "payment_status": f.payment_status,
            "payment_mode": f.payment_mode,
            "razorpay_payment_id": f.razorpay_payment_id,
            "cheque_no": f.cheque_no,
            "dd_no": f.dd_no,
            "file_path": f.file_path,
            "created_at": f.created_at,
        }
        for f in fees
    ]

# Download fee PDF by student id and installment no
@router.get("/download/{student_id}/{installment_no}")
def download_fee(student_id: str, installment_no: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter_by(student_id=student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    fee = db.query(Fee).filter_by(student_id=student_id, installment_no=installment_no).first()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found for this installment")

    if not fee.file_path or not os.path.exists(fee.file_path):
        raise HTTPException(status_code=404, detail="Fee file not found")

    return FileResponse(path=fee.file_path, filename=f"fee_{student_id}_{installment_no}.pdf", media_type='application/pdf')

# Delete fee by id
@router.delete("/delete-by/{fee_id}", response_model=dict)
def delete_fee(fee_id: str, db: Session = Depends(get_db)):
    fee = db.query(Fee).filter_by(fee_id=fee_id).first()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")

    try:
        if fee.file_path and os.path.exists(fee.file_path):
            os.remove(fee.file_path)
    except Exception:
        pass

    db.delete(fee)
    db.commit()
    return {"detail": "Fee deleted"}

# Update fee by id
@router.put("/update-by/{fee_id}", response_model=dict)
def update_fee(fee_id: str, request: UpdateFeeRequest, db: Session = Depends(get_db)):
    fee = db.query(Fee).filter_by(fee_id=fee_id).first()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee not found")
        
    fee.amount = request.amount
    fee.payment_status = request.payment_status
    fee.payment_type = request.payment_type
    if request.payment_type == 'installment' and request.installment_no is not None:
        fee.installment_no = request.installment_no
    else:
        fee.installment_no = 0
        
    fee.updated_at = datetime.utcnow()
    db.commit()
    
    return {"detail": "Fee updated successfully"}


