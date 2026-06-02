from db import engine
from sqlalchemy import text

def alter_table():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE salaries ADD COLUMN fixed_salary FLOAT DEFAULT 0.0;"))
            conn.execute(text("ALTER TABLE salaries ADD COLUMN commission_per_student FLOAT DEFAULT 0.0;"))
            conn.execute(text("ALTER TABLE salaries ADD COLUMN referrals_admitted INTEGER DEFAULT 0;"))
            conn.execute(text("ALTER TABLE salaries ADD COLUMN total_salary FLOAT DEFAULT 0.0;"))
            conn.execute(text("ALTER TABLE salaries ADD COLUMN payment_mode VARCHAR DEFAULT 'NEFT';"))
            conn.execute(text("ALTER TABLE salaries ADD COLUMN transaction_id VARCHAR;"))
            conn.execute(text("ALTER TABLE salaries ADD COLUMN status VARCHAR DEFAULT 'Paid';"))
            conn.commit()
            print("Successfully altered table")
        except Exception as e:
            print("Error altering table:", e)

if __name__ == '__main__':
    alter_table()
