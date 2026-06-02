import sys
sys.path.append('d:/VWings24x7-App-Backend')
from db import engine
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE payouts ADD COLUMN file_path VARCHAR;"))
        conn.commit()
        print("Successfully added file_path column to payouts table.")
    except Exception as e:
        print(f"Error: {e}")
