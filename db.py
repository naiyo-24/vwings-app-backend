from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Get database credentials from environment
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# Create database URL
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL, echo=True)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Import all models here to ensure they are registered with SQLAlchemy's Base
from models.auth import admin_models, student_models, teacher_models, counsellor_models
from models.courses import course_models
from models.aboutus import about_us_models
from models.help_center import help_center_models
from models.admission import admission_code_models
from models.admission import admission_enquiry_models
from models.ads import ads_models
from models.announcement import announcement_models
from models.classroom import classroom_models
from models.classroom import class_chat_models
from models.commission import commission_models
from models.salary import salary_models
from models.fees import fees_models
from models.admission import student_admission_models
# Function to create all tables
def create_tables():
    Base.metadata.create_all(bind=engine)
