import sqlite3

conn = sqlite3.connect("d:\\VWings24x7-App-Backend\\vwings.db")
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", cursor.fetchall())
conn.close()
