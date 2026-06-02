from sqlalchemy import text
from db import engine

def add_columns():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE counsellors ADD COLUMN commission_type VARCHAR(50) DEFAULT 'Fixed'"))
        except Exception as e:
            print("Error adding commission_type:", e)

        try:
            conn.execute(text("ALTER TABLE counsellors ADD COLUMN commission_value FLOAT DEFAULT 0.0"))
        except Exception as e:
            print("Error adding commission_value:", e)

        try:
            conn.execute(text("ALTER TABLE counsellors ADD COLUMN status VARCHAR(50) DEFAULT 'Active'"))
        except Exception as e:
            print("Error adding status:", e)

        conn.commit()

if __name__ == '__main__':
    add_columns()
