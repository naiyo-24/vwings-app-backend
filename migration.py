from sqlalchemy import create_engine
from sqlalchemy.sql import text
import os
from dotenv import load_dotenv
load_dotenv()

DB_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
engine = create_engine(DB_URL)
with engine.connect() as con:
    con.execute(text("ALTER TABLE fees ADD COLUMN IF NOT EXISTS payment_mode VARCHAR DEFAULT 'online';"))
    con.execute(text("ALTER TABLE fees ADD COLUMN IF NOT EXISTS cheque_no VARCHAR;"))
    con.execute(text("ALTER TABLE fees ADD COLUMN IF NOT EXISTS dd_no VARCHAR;"))
    con.commit()
print("Migration done!")
