import sqlite3

def add_columns():
    conn = sqlite3.connect('vwings.db')
    cursor = conn.cursor()
    
    # Add new columns to counsellors
    try:
        cursor.execute("ALTER TABLE counsellors ADD COLUMN commission_type VARCHAR(50) DEFAULT 'Fixed'")
    except Exception as e:
        print(e)
        
    try:
        cursor.execute("ALTER TABLE counsellors ADD COLUMN commission_value FLOAT DEFAULT 0.0")
    except Exception as e:
        print(e)

    try:
        cursor.execute("ALTER TABLE counsellors ADD COLUMN status VARCHAR(50) DEFAULT 'Active'")
    except Exception as e:
        print(e)

    conn.commit()
    conn.close()

if __name__ == '__main__':
    add_columns()
