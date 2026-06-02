from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from uuid import uuid4
from services.report_id_generator import generate_report_id
from db import get_db
from models.help_center.help_center_models import HelpCenter
from routes.notification.notification_routes import create_notification

router = APIRouter(prefix="/api/helpcenter", tags=["HelpCenter"])


class HelpCenterCreate(BaseModel):
    report_id: Optional[str] = None
    name: Optional[str] = None
    phone_no: Optional[str] = None
    email: Optional[str] = None
    problem_description: Optional[str] = None
    status: Optional[str] = None


class HelpCenterStatusUpdate(BaseModel):
    status: str


class HelpCenterResponse(HelpCenterCreate):
    id: int

    class Config:
        from_attributes = True


# Create a new help report
@router.post("/create", response_model=HelpCenterResponse)
def create_help_report(payload: HelpCenterCreate, db: Session = Depends(get_db)):
    # generate report id using service if not provided
    report_id = payload.report_id or generate_report_id(db)
    help_item = HelpCenter(
        report_id=report_id,
        name=payload.name,
        phone_no=payload.phone_no,
        email=payload.email,
        problem_description=payload.problem_description,
        status=payload.status or "open",
    )
    db.add(help_item)
    db.commit()
    db.refresh(help_item)
    
    create_notification(
        "New Help Request",
        f"A new support request was opened by {payload.name}.",
        "admin"
    )
    
    return help_item

# List all help reports
@router.get("/get-all", response_model=List[HelpCenterResponse])
def list_help_reports(db: Session = Depends(get_db)):
    items = db.query(HelpCenter).all()
    return items

# Get help report by report_id
@router.get("/get-by/{report_id}", response_model=HelpCenterResponse)
def get_help_report(report_id: str, db: Session = Depends(get_db)):
    item = db.query(HelpCenter).filter(HelpCenter.report_id == report_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Help report not found")
    return item

# Update help report status by report_id
@router.put("/update-status/{report_id}", response_model=HelpCenterResponse)
def update_help_status(report_id: str, payload: HelpCenterStatusUpdate, db: Session = Depends(get_db)):
    item = db.query(HelpCenter).filter(HelpCenter.report_id == report_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Help report not found")
    item.status = payload.status
    db.add(item)
    db.commit()
    db.refresh(item)
    
    create_notification(
        "Help Request Updated",
        f"The status of help request {report_id} has been changed to {payload.status}.",
        "admin"
    )
    
    return item

# Delete help report by report_id
@router.delete("/delete/{report_id}")
def delete_help_report(report_id: str, db: Session = Depends(get_db)):
    item = db.query(HelpCenter).filter(HelpCenter.report_id == report_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Help report not found")
    db.delete(item)
    db.commit()
    return {"detail": "Deleted successfully"}
