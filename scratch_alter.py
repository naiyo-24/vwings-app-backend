import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE classrooms ADD COLUMN meet_link VARCHAR;"))
        conn.execute(text("ALTER TABLE classrooms ADD COLUMN class_date VARCHAR;"))
        conn.execute(text("ALTER TABLE classrooms ADD COLUMN class_time VARCHAR;"))
        conn.commit()
    print("Successfully added columns to classrooms.")
except Exception as e:
    print(f"Error: {e}")
