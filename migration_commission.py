from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)

def alter_db():
    queries = [
        "ALTER TABLE counsellors ADD COLUMN commission_per_student FLOAT DEFAULT 0.0",
        "ALTER TABLE commission_slips ADD COLUMN payment_mode VARCHAR DEFAULT 'NEFT'",
        "ALTER TABLE commission_slips ADD COLUMN transaction_id VARCHAR",
        "ALTER TABLE commission_slips ADD COLUMN status VARCHAR DEFAULT 'Paid'"
    ]

    for q in queries:
        with engine.connect() as conn:
            with conn.begin():
                try:
                    conn.execute(text(q))
                    print(f"Success: {q}")
                except Exception as e:
                    print(f"Error on {q}: {e}")

if __name__ == '__main__':
    alter_db()
