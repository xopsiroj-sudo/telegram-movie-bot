import sqlite3
import os

DB_PATH = "movies.db"

def check():
    if not os.path.exists(DB_PATH):
        print(f"Database file {DB_PATH} not found!")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get schema
        cursor.execute("PRAGMA table_info(movies);")
        columns = cursor.fetchall()
        print("Schema (PRAGMA table_info):")
        for col in columns:
            print(col)
        
        # Check counts
        cursor.execute("SELECT COUNT(*) FROM movies;")
        count = cursor.fetchone()[0]
        print(f"\nTotal movies: {count}")
        
        # Check first few rows with column names
        cursor.execute("SELECT * FROM movies LIMIT 5;")
        rows = cursor.fetchall()
        col_names = [description[0] for description in cursor.description]
        print(f"\nFirst 5 rows (Column Names: {col_names}):")
        for row in rows:
            print(row)
            
        # Test a search for code '1'
        print("\nTesting search for code '1'...")
        cursor.execute("SELECT file_identifier, type, title FROM movies WHERE code = '1'")
        res = cursor.fetchone()
        print(f"Result for code '1': {res}")
        
        # Test a search for title LIKE '%kino%' (if any)
        cursor.execute("SELECT file_identifier, type, title FROM movies WHERE title LIKE '%kino%' LIMIT 5")
        res_like = cursor.fetchall()
        print(f"Results for title LIKE '%kino%': {res_like}")
        
        conn.close()
    except Exception as e:
        print(f"Error during check: {e}")

if __name__ == "__main__":
    check()
