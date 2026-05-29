from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from db import get_db
from models.announcement.announcement_models import Announcement
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/announcements", tags=["Announcements"])

# Pydantic Schemas
class AnnouncementCreate(BaseModel):
	headline: str
	description: str
	role: Optional[str] = "student"
	target_id: Optional[str] = None
	active_status: Optional[bool] = True

class AnnouncementUpdate(BaseModel):
	headline: Optional[str]
	description: Optional[str]
	target_id: Optional[str]
	active_status: Optional[bool]

class AnnouncementOut(BaseModel):
	announcement_id: int
	headline: str
	description: str
	role: str
	target_id: Optional[str] = None
	active_status: bool
	created_at: datetime
	updated_at: datetime

	class Config:
		from_attributes = True


# Create announcement for specific role
@router.post("/create/role/{role}", response_model=AnnouncementOut, status_code=status.HTTP_201_CREATED)
def create_announcement_for_role(role: str, payload: AnnouncementCreate, db: Session = Depends(get_db)):
	data = payload.dict()
	data["role"] = role
	announcement = Announcement(**data)
	db.add(announcement)
	db.commit()
	db.refresh(announcement)
	return announcement


@router.get("/get-all/role/{role}", response_model=List[AnnouncementOut])
def get_all_announcements_for_role(role: str, db: Session = Depends(get_db)):
	return db.query(Announcement).filter(Announcement.role == role).all()


@router.get("/get-by/role/{role}/{announcement_id}", response_model=AnnouncementOut)
def get_announcement_for_role(role: str, announcement_id: int, db: Session = Depends(get_db)):
	ann = db.query(Announcement).filter(Announcement.announcement_id == announcement_id, Announcement.role == role).first()
	if not ann:
		raise HTTPException(status_code=404, detail="Announcement not found for role")
	return ann


@router.put("/update-by/role/{role}/{announcement_id}", response_model=AnnouncementOut)
def update_announcement_for_role(role: str, announcement_id: int, payload: AnnouncementUpdate, db: Session = Depends(get_db)):
	announcement = db.query(Announcement).filter(Announcement.announcement_id == announcement_id, Announcement.role == role).first()
	if not announcement:
		raise HTTPException(status_code=404, detail="Announcement not found for role")
	for key, value in payload.dict(exclude_unset=True).items():
		setattr(announcement, key, value)
	db.commit()
	db.refresh(announcement)
	return announcement


@router.delete("/delete-by/role/{role}/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_announcement_for_role(role: str, announcement_id: int, db: Session = Depends(get_db)):
	announcement = db.query(Announcement).filter(Announcement.announcement_id == announcement_id, Announcement.role == role).first()
	if not announcement:
		raise HTTPException(status_code=404, detail="Announcement not found for role")
	db.delete(announcement)
	db.commit()
	return

# Get all announcements
@router.get("/get-all", response_model=List[AnnouncementOut])
def get_all_announcements(db: Session = Depends(get_db)):
	return db.query(Announcement).all()


# Bulk delete announcements
class BulkDeleteRequest(BaseModel):
	ids: List[int]

@router.delete("/delete/bulk", status_code=status.HTTP_204_NO_CONTENT)
def bulk_delete_announcements(payload: BulkDeleteRequest, db: Session = Depends(get_db)):
	db.query(Announcement).filter(Announcement.announcement_id.in_(payload.ids)).delete(synchronize_session=False)
	db.commit()
	return
