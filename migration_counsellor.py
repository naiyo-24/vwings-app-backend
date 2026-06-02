import sqlite3

def migrate():
    conn = sqlite3.connect("d:\\VWings24x7-App-Backend\\vwings.db")
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE counsellors ADD COLUMN commission_per_student INTEGER DEFAULT 0")
        print("Added commission_per_student to counsellors")
    except Exception as e:
        print(e)
        
    try:
        cursor.execute("ALTER TABLE commission_slips ADD COLUMN students_admitted INTEGER DEFAULT 0 NOT NULL")
        cursor.execute("ALTER TABLE commission_slips ADD COLUMN commission_per_student INTEGER DEFAULT 0 NOT NULL")
        cursor.execute("ALTER TABLE commission_slips ADD COLUMN total_payout INTEGER DEFAULT 0 NOT NULL")
        cursor.execute("ALTER TABLE commission_slips ADD COLUMN transaction_id VARCHAR")
        print("Added new fields to commission_slips")
    except Exception as e:
        print(e)
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate()
