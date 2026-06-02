import psycopg2
import os

try:
    conn = psycopg2.connect(
        host="localhost",
        port="5432",
        user="postgres",
        password="password",
        database="vwings24x7_db"
    )
    cursor = conn.cursor()
    
    queries = [
        "ALTER TABLE counsellors ADD COLUMN IF NOT EXISTS commission_per_student FLOAT DEFAULT 0.0;",
        "ALTER TABLE commission_slips ADD COLUMN IF NOT EXISTS admitted_students INTEGER DEFAULT 0;",
        "ALTER TABLE commission_slips ADD COLUMN IF NOT EXISTS per_student_commission FLOAT DEFAULT 0.0;",
        "ALTER TABLE commission_slips ADD COLUMN IF NOT EXISTS total_amount FLOAT DEFAULT 0.0;"
    ]
    
    for query in queries:
        try:
            cursor.execute(query)
            conn.commit()
            print("Successfully executed:", query)
        except Exception as e:
            conn.rollback()
            print("Error executing:", query)
            print("Error:", e)
            
    cursor.close()
    conn.close()
except Exception as e:
    print("Connection failed:", e)
