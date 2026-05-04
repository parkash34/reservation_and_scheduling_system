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
    
    def is_with_opening_hours(self, requrest_time: str) -> dict:
        """Checks if requested time is within opening hours."""

        try:
            config = self.get_config()

            opening = datetime.strptime(config["opening_time"], "%H:%M").time()
            closing = datetime.strptime(config["closing_time"], "%H:%M").time()
            requested = datetime.strptime(requrest_time, "%H:%M").time()

            last_booking_minutes = (
                datetime.combine(datetime.today(), closing) -
                timedelta(minutes=config["slot_duration"])
            ).time()

            if requested < opening:
                return {
                    "valid": False,
                    "message": f"We open at {config['opening_time']}. Please book after that."
                }
            if requested > last_booking_minutes:
                return {
                    "valid": False,
                    "message": f"Last booking is at {last_booking_minutes.strftime('%H:%M')}. We close at {config['closing_time']}."
                }
            
            return {"valid" : True}
        
        except ValueError:
            return {
                "valid": False,
                "message": "Invalid time format. Please use HH:MM format like 19:00"
            }
    
    def is_future_date(self, booking_date: str, booking_time: str) -> dict:
        """Checks if booking is in the future."""
        try:
            booking_datetime = datetime.strptime(
                f"{booking_date} {booking_time}",
                "%Y-%m-%d %H:%M"
            )

            if booking_datetime < datetime.now():
                return {
                    "valid": False,
                    "message" : "Cannot book in the past. Pleasae choose a future date."
                }
            
            return {"valid": True}
        
        except ValueError:
            return {
                "valid": False,
                "message": "Invalid date formate. Please use YYYY-MM-DD like 2026-05-04"
            }
        
    
    def validate_capacity(self, people: int, date: str, time: str) -> dict:
        """Checks if restaurant has capacity for requested people."""
        config = self.get_config()
        max_capacity = config["max_capacity"]
        slot_duration = config["slot_duration"]

        with get_db() as db:
            cursor = db.cursor()
            cursor.execute("""
                SELECT COALESCE(SUM(people), 0) as total_booked
                FROM reservations
                WHERE date = ?
                AND status = 'confirmed'
                AND time BETWEEN
                    time(?, '-' || ? || ' minutes')
                    AND time(?, '+' || ? || ' minutes')
            """, (date, time, slot_duration, time, slot_duration))

            row = cursor.fetchone()
            total_booked = row["total_booked"]
            remaining = max_capacity - total_booked

            if people > remaining:
                return {
                    "valid": False,
                    "available_capacity" : remaining,
                    "message": f"Sorry we only have space for {remaining} more people at that time." 
                }
            
            return {
                "valid" : True,
                "available_capacity": remaining
            } 

    def check_availability(self, date, time: str, people) -> dict:
        """Full availability check combining all validations."""

        time_result = self.normalize_time(time)
        if not time_result["valid"]:
            return {"valid": False, "message": time_result["message"]}
    
        normalized_time = time_result["normalized"]

        time_check = self.is_within_opening_hours(normalized_time)
        if not time_check["valid"]:
            return time_check
        
        date_check = self.is_future_date(date, normalized_time)
        if not date_check["valid"]:
            return date_check

        capacity_check = self.validate_capacity(people, date, normalized_time)
        if not capacity_check["valid"]:
            return capacity_check

        return {
            "valid": True,
            "message": f"Table available for {people} people on {date} at {normalized_time}",
            "available_capacity": capacity_check["available_capacity"]
        }
        
    def create_reservation(self, customer_name, date, time_str, people, customer_phone, customer_email, special_requirement) -> dict:
        return None

    def book_with_validation(self, customer_name: str, date: str, time: str, people: int, customer_phone: str = None, customer_email: str = None, special_requirement: str = None ) -> dict:
        """Complete booking with all validations."""

        availability = self.check_availability(date, time, people)
        if not availability["valid"]:
            return {
                "success": False,
                "message": availability["message"]
            }

        result = self.create_reservation(
            customer_name=customer_name,
            date=date,
            time=time,
            people=people,
            customer_phone=customer_phone,
            customer_email=customer_email,
            special_requirement=special_requirement
        )

        return result
    
    def get_reservations_by_name(self, name) -> dict:
        return None
    def get_all_reservations(self, date=None) -> dict:
        return None
    def update_reservation(self, reference, new_date=None, new_time=None, new_people=None) -> dict:
        return None
    def cancel_reservation(self, reference) -> dict:
        return None
    
