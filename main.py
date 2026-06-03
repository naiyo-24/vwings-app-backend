from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from db import create_tables
from routes.auth import admin_routes, student_routes, teacher_routes, counsellor_routes
from routes.courses import course_routes
from routes.aboutus import about_us_routes
from routes.help_center import help_center_routes
from routes.admission import admission_code_routes
from routes.admission import admission_enquiry_routes
from routes.ads import ads_routes
from routes.announcement import announcement_routes
from routes.classroom import classroom_routes
from routes.classroom import class_chat_routes
from routes.commission import commission_routes
from routes.salary import salary_routes
from routes.fees import fees_routes
from routes.notification import notification_routes

# Create FastAPI app
app = FastAPI(
    title="VWINGS24X7 Backend API",
    description="Backend API for Admin Management",
    version="1.0.0",
    swagger_ui_parameters={"favicon_url": "/static/logo.png"},
    redoc_favicon_url="/static/logo.png",
)

# Configure CORS to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Mount /static and /uploads as static files so assets can be accessed via URL
app.mount("/static", StaticFiles(directory="static"), name="static")
# /uploads will serve uploaded files like profile photos, classroom photos, salary slips, fee receipts, etc.
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# Serve favicon for browsers requesting /favicon.ico
@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse("static/logo.png")

# Health check endpoint
@app.get("/health", tags=["Health"])
def health_check():
    """
    Health check endpoint to verify server status
    """
    return {
        "status": "healthy",
        "message": "Server is running successfully"
    }

from routes.search import search_routes

# Register routers
app.include_router(admin_routes.router)
app.include_router(course_routes.router)
app.include_router(about_us_routes.router)
app.include_router(help_center_routes.router)
app.include_router(student_routes.router)
app.include_router(teacher_routes.router)
app.include_router(counsellor_routes.router)
app.include_router(admission_code_routes.router)
app.include_router(admission_enquiry_routes.router)
app.include_router(ads_routes.router)
app.include_router(announcement_routes.router)
app.include_router(classroom_routes.router)
app.include_router(class_chat_routes.router)
app.include_router(commission_routes.router)
app.include_router(salary_routes.router)
app.include_router(fees_routes.router)
app.include_router(notification_routes.router)
app.include_router(search_routes.router)

# Create database tables on startup
@app.on_event("startup")
def on_startup():
    print("Creating database tables...")
    create_tables()
    
    # Auto-migrate payment_mode column
    from db import engine
    from sqlalchemy import text
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE fees ADD COLUMN payment_mode VARCHAR DEFAULT 'online'"))
            print("Successfully added payment_mode column to fees table.")
    except Exception as e:
        # Expected if column already exists
        pass

    # Auto-migrate salaries columns
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE salaries ADD COLUMN fixed_salary FLOAT DEFAULT 0.0"))
            conn.execute(text("ALTER TABLE salaries ADD COLUMN commission_per_student FLOAT DEFAULT 0.0"))
            conn.execute(text("ALTER TABLE salaries ADD COLUMN referrals_admitted INTEGER DEFAULT 0"))
            conn.execute(text("ALTER TABLE salaries ADD COLUMN total_salary FLOAT DEFAULT 0.0"))
            conn.execute(text("ALTER TABLE salaries ADD COLUMN payment_mode VARCHAR DEFAULT 'NEFT'"))
            conn.execute(text("ALTER TABLE salaries ADD COLUMN transaction_id VARCHAR"))
            conn.execute(text("ALTER TABLE salaries ADD COLUMN status VARCHAR DEFAULT 'Paid'"))
            conn.execute(text("ALTER TABLE salaries ALTER COLUMN file_path DROP NOT NULL"))
            print("Successfully added new columns to salaries table.")
    except Exception as e:
        pass
        
    print("Database tables created successfully!")

# Root endpoint
@app.get("/", tags=["Root"])
def read_root():
    return {
        "message": "Welcome to VWINGS24X7 Backend API",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    # Run on all IPs (0.0.0.0) to ensure accessibility
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
