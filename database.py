import sqlite3
import os
from config import DB_FILE, SEEDS_DIR

def init_db():
    print("   → Connecting to database...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    if not os.path.exists(SEEDS_DIR):
        os.makedirs(SEEDS_DIR)
        print(f"   → Created seeds directory at: {SEEDS_DIR}")

    sql_files = sorted([f for f in os.listdir(SEEDS_DIR) if f.endswith('.sql')])

    if not sql_files:
        print("   ⚠️  No .sql files found in seeds/ folder")
    else:
        for sql_file in sql_files:
            file_path = os.path.join(SEEDS_DIR, sql_file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    sql_script = f.read()
                    cursor.executescript(sql_script)
                    print(f"   ✓ Executed: {sql_file}")
            except Exception as e:
                print(f"   ✗ Error executing {sql_file}: {e}")

                conn.commit()
                conn.close()
                print("✅ Database initialization completed.\n")


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn