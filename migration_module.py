import sys
import os
sys.path.append(r"d:\VWings24x7-App-Backend")
from db import engine, Base
from models.admission.student_admission_models import StudentAdmission
from models.commission.commission_models import CommissionLedger, Payout
from models.auth.counsellor_models import Counsellor
import sqlite3

# This creates tables if they don't exist
Base.metadata.create_all(bind=engine)

# Add new columns to counsellors if they don't exist using alter table
def alter_counsellors():
    conn = sqlite3.connect(r'd:\VWings24x7-App-Backend\vwings.db')
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE counsellors ADD COLUMN commission_type VARCHAR")
    except sqlite3.OperationalError:
        pass # Column might already exist
    
    try:
        cursor.execute("ALTER TABLE counsellors ADD COLUMN commission_value FLOAT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE counsellors ADD COLUMN status VARCHAR DEFAULT 'active'")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

alter_counsellors()
print("Migration completed.")
