import sqlite3
import random
from contextlib import contextmanager
from datetime import timedelta, datetime


@contextmanager
def get_db():
    connect = sqlite3.connect("restaurant.db")
    connect.row_factory = sqlite3.Row
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

    def init_db(self):
        """Create tables if they don't exist."""
        with get_db() as db:
            db.row_factory = sqlite3.Row
            cursor = db.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reservations (
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

            cursor.execute("""
                INSERT OR IGNORE INTO restaurant_config
                (id, max_capacity, opening_time, closing_time, slot_duration)
                VALUES (1, 50, '12:00', '23:00', 90)
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
        
    def normalize_time(self, time: str) -> dict:
        """Converts any time format to HH:MM 24 hour format."""

        time = time.strip().upper()
    
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
                parsed = datetime.strptime(time, fmt)
                return {
                    "valid": True,
                    "normalized": parsed.strftime("%H:%M")
                }
            except ValueError:
                continue

        return {
            "valid" : False,
            "message" : f"Could not understand time '{time}'. Please use format like 10:00 PM or 22:00"
        }
    
    def is_within_opening_hours(self, requested_time: str) -> dict:
        """Checks if requested time is within opening hours."""

        try:
            config = self.get_config()

            opening = datetime.strptime(config["opening_time"], "%H:%M").time()
            closing = datetime.strptime(config["closing_time"], "%H:%M").time()
            requested = datetime.strptime(requested_time, "%H:%M").time()

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
                    "message" : "Cannot book in the past. Please choose a future date."
                }
            
            return {"valid": True}
        
        except ValueError:
            return {
                "valid": False,
                "message": "Invalid date format. Please use YYYY-MM-DD like 2026-05-04"
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

    def check_availability(self, date: str, time: str, people) -> dict:
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
        
    def create_reservation(self, customer_name: str, date: str, time: str, people: int, customer_phone: str = None, customer_email: str = None, special_requirement: str= None) -> dict:
        """Creates reservation for customers"""
        try:
            for attempt in range(5):
                reference = random.randint(10000, 99999)
                try:
                    with get_db() as db:
                        cursor = db.cursor()
                        cursor.execute("""
                            INSERT INTO reservations
                            (customer_name, date, time, people, reference)
                            VALUES (?, ?, ?, ?, ?)
                        """, (customer_name, date, time, people, reference))
                    
                    return {
                        "success": True,
                        "reference": reference
                    }
                except sqlite3.IntegrityError:
                    continue 

            return {"success": False, "error": "Could not generate unique reference"}

        except Exception as e:
            return {"success": False, "error": str(e)}

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

    def get_reservation_by_reference(self, reference: int) -> dict:
        """Gets reservation by reference number."""
        with get_db() as db:
            cursor = db.cursor()
            cursor.execute("""
                SELECT * FROM reservations
                WHERE reference = ? AND status = 'confirmed'
            """, (reference,))
            row = cursor.fetchone()

            if not row:
                return {"found": False, "message": f"No reservation found with reference {reference}"}

            return {
                "found": True,
                "reservation": {
                    "reference": row["reference"],
                    "customer_name": row["customer_name"],
                    "date": row["date"],
                    "time": row["time"],
                    "people": row["people"],
                    "special_requirement": row["special_requirement"],
                    "status": row["status"]
                }
            }
    
    def get_reservations_by_name(self, name: str) -> dict:
        """Gets all reservations for a customer."""

        with get_db() as db:
            cursor = db.cursor()
            cursor.execute("""
                SELECT * FROM reservations
                WHERE customer_name LIKE ? AND status = 'confirmed'
                ORDER BY date, time
            """, (f"%{name}%",))
            rows = cursor.fetchall()

            if not rows:
                return {"found": False, "message": f"No reservations found for {name}"}

            reservations = []
            for row in rows:
                reservations.append({
                    "reference": row["reference"],
                    "date": row["date"],
                    "time": row["time"],
                    "people": row["people"]
                })

            return {"found": True, "reservations": reservations}
        
    def get_all_reservations(self, date: str=None) -> dict:
        """Gets all confirmed reservations optionally filtered by date."""

        with get_db() as db:
            cursor = db.cursor()
            if date:
                cursor.execute("""
                    SELECT * FROM reservations
                    WHERE date = ? AND status = 'confirmed'
                    ORDER BY time
                """, (date,))
            else:
                cursor.execute("""
                    SELECT * FROM reservations
                    WHERE status = 'confirmed'
                    ORDER BY date, time
                """)

            rows = cursor.fetchall()
            reservations = []
            for row in rows:
                reservations.append({
                    "reference": row["reference"],
                    "customer_name": row["customer_name"],
                    "date": row["date"],
                    "time": row["time"],
                    "people": row["people"],
                    "status": row["status"]
                })

            return {
                "total": len(reservations),
                "reservations": reservations
            }
        
    def update_reservation(self, reference : int, new_date: str= None, new_time: str= None, new_people: str= None) -> dict:
        """Updates an existing reservation."""

        with get_db() as db:
            cursor = db.cursor()

            cursor.execute("""
                SELECT * FROM reservations
                WHERE reference = ? AND status = 'confirmed'
            """, (reference,))
            row = cursor.fetchone()

            if not row:
                return {"success": False, "message": "Reservation not found"}
        
            updates = []
            values = []

            if new_date:
                updates.append("date = ?")
                values.append(new_date)
            if new_time:
                updates.append("time = ?")
                values.append(new_time)
            if new_people:
                updates.append("people = ?")
                values.append(new_people)

            if not updates:
                return {"success": False, "message": "Nothing to update"}

            values.append(reference)
            query = f"UPDATE reservations SET {', '.join(updates)} WHERE reference = ?"

            cursor.execute(query, values)

            return {
                "success": True,
                "message": f"Reservation {reference} updated successfully"
            }
    
    def cancel_reservation(self, reference:int) -> dict:
        """Cancels a reservation by setting status to cancelled."""

        with get_db() as db:
            cursor = db.cursor()
            cursor.execute("""
                SELECT * FROM reservations
                WHERE reference = ? AND status = 'confirmed'
            """, (reference,))
            row = cursor.fetchone()

            if not row:
                return {"success": False, "message": f"No active reservation found with reference {reference}"}
            
            cursor.execute("""
                UPDATE reservations
                SET status = 'cancelled'
                WHERE reference = ?
            """, (reference,))

            return {
                "success": True,
                "message": f"Reservation {reference} cancelled successfully",
                "customer_name": row["customer_name"],
                "date": row["date"],
                "time": row["time"]
            }
    
