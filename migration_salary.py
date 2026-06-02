import sqlite3
import os

def upgrade():
    db_path = r'd:\VWings24x7-App-Backend\vwings.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE salaries ADD COLUMN fixed_salary FLOAT DEFAULT 0.0;")
        cursor.execute("ALTER TABLE salaries ADD COLUMN commission_per_student FLOAT DEFAULT 0.0;")
        cursor.execute("ALTER TABLE salaries ADD COLUMN referrals_admitted INTEGER DEFAULT 0;")
        cursor.execute("ALTER TABLE salaries ADD COLUMN total_salary FLOAT DEFAULT 0.0;")
        cursor.execute("ALTER TABLE salaries ADD COLUMN payment_mode VARCHAR DEFAULT 'NEFT';")
        cursor.execute("ALTER TABLE salaries ADD COLUMN transaction_id VARCHAR;")
        cursor.execute("ALTER TABLE salaries ADD COLUMN status VARCHAR DEFAULT 'Paid';")
        conn.commit()
        print("Migration successful.")
    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    upgrade()
