import sqlite3
import random
from contextlib import contextmanager
from datetime import timedelta, datetime


@contextmanager
def get_db():
    connect = sqlite3.connect("restaurant.db")
    try:
        yield connect
        connect.commit()
    except Exception as e:
        connect.rollback()
        raise e
    finally:
        connect.close()

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()

    def init_db():
        """Create tables if they don't exist."""
        with get_db() as db:
            cursor = db.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reservation(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_name TEXT NOT NULL,
                    customer_phone TEXT,
                    customer_email TEXT,
                    date TEXT NOT NULL,
                    time TEXT NOT NULL,
                    people INTEGER NOT NULL,
                    special_requirement TEXT,
                    status TEXT DEFAULT 'confirmed',
                    reference INTEGER UNIQUE NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
        """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS restaurant_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    max_capacity INTEGER DEFAULT 50,
                    opening_time TEXT DEFAULT "12:00",
                    closing_time TEXT DEFAULT "23:00",
                    slot_duration INTEGER DEFAULT "90"
                )
        """)
    def get_config(self) -> dict:
        """Get restaurant configuration."""
        with get_db() as db:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM restaurant_config WHERE id = 1")
            row = cursor.fetchone()
            return {
                "max_capacity" : row["max_capacity"],
                "opening_time" : row["opening_time"],
                "closing_time" : row["closing_time"],
                "slot_duration" : row["slot_duration"]
            }
        
    def normalize_time(self, time_str: str) -> dict:
        """Converts any time format to HH:MM 24 hour format."""

        time_str = time_str.strip().upper()
    
        formats = [
            "%I:%M %p",   # 10:00 PM
            "%I %p",      # 10 PM
            "%H:%M",      # 22:00
            "%I:%M%p",    # 10:00PM
            "%I%p",       # 10PM
            "%H.%M",      # 22.00
            "%I.%M %p",   # 10.00 PM
        ]

        for fmt in formats:
            try:
                self.parsed = datetime.strptime(time_str, fmt)
                return {
                    "valid": True,
                    "normalized": self.parsed.strftime("%H:%M")
                }
            except ValueError:
                continue
        return {
            "valid" : False,
            "message" : f"Could not understand time '{time_str}'. Please use format like 10:00 PM or 22:00"
        }
