# db_init.py (database)
import sqlite3

DB_PATH = r"D:\demo\app\database\restaurant.db"

def initialize_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reservations (
        reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,        
        intent TEXT,
        user_name TEXT ,
        email_id TEXT,
        num_persons INTEGER,
        reservation_type TEXT,
        res_date TEXT,
        res_time TEXT,
        status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'confirmed', 'cancelled')),        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(res_date, res_time, reservation_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interaction_logs (
        log_id TEXT PRIMARY KEY,
        reservation_id TEXT,
        user_input TEXT NOT NULL,
        intent TEXT,
        llm_response TEXT NOT NULL,
        missing_fields TEXT,
        fallback_triggered BOOLEAN DEFAULT FALSE,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        error TEXT,
        FOREIGN KEY (reservation_id) REFERENCES reservations(reservation_id) ON DELETE SET NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS evaluation_metrics (
        eval_id TEXT PRIMARY KEY,
        reservation_id TEXT NOT NULL,
        extracted_fields TEXT,
        validation_passed BOOLEAN,
        availability_checked BOOLEAN,
        alt_suggested BOOLEAN,
        final_status TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (reservation_id) REFERENCES reservations(reservation_id) ON DELETE CASCADE
    );
    """)

if __name__ == "__main__":
    initialize_database()
    print("Database initialized using app\database\db_init.py")