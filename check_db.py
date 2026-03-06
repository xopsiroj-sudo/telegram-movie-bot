import sqlite3
import os

DB_PATH = "movies.db"

if not os.path.exists(DB_PATH):
    print(f"Database file {DB_PATH} not found!")
    exit(1)

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tables: {tables}")
    
    # Check movies
    cursor.execute("SELECT * FROM movies LIMIT 20;")
    movies = cursor.fetchall()
    print(f"Movies (first 20):")
    for m in movies:
        print(m)
        
    # Check search logic
    test_code = "1" # Example code
    cursor.execute("SELECT file_identifier, type, title FROM movies WHERE code = ?", (test_code,))
    res = cursor.fetchone()
    print(f"Search result for code '{test_code}': {res}")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
