# Bella Italia — Reservation & Scheduling System

A production ready restaurant reservation system built with FastAPI,
SQLite and LangGraph. Features full validation including time checking,
capacity management and conflict detection. Includes both a direct API
and an AI powered chatbot for managing bookings.

## Features

- Full time validation — rejects bookings outside opening hours
- Capacity management — tracks total people per time slot
- Conflict detection — prevents overbooking
- Time normalization — accepts any time format like 7 PM or 19:00
- Soft delete — cancellations preserved in database as history
- Dynamic updates — change only what needs changing
- AI chatbot — natural language booking via conversation
- Direct API — programmatic access for all operations
- Restaurant config — manage settings from database

## Tech Stack

| Technology | Purpose |
|---|---|
| Python | Core programming language |
| FastAPI | Backend web framework |
| SQLite | Reservation database |
| LangGraph | AI agent framework |
| LangChain | AI tooling |
| Groq API | AI language model |
| LLaMA 3.3 70B | AI model |
| Pydantic | Data validation |
| python-dotenv | Environment variable management |

## Project Structure
```
reservation-system/
│
├── env/
├── main.py
├── database.py
├── .env
└── requirements.txt
```
## Setup

1. Clone the repository
```
git clone https://github.com/yourusername/bella-italia-reservation-system
```
2. Create and activate virtual environment
```
python -m venv env
env\Scripts\activate
```
3. Install dependencies
```
pip install -r requirements.txt
```
4. Create `.env` file
```
API_KEY=your_groq_api_key
```
5. Run the server
```
uvicorn main:app --reload
```
## API Endpoints

### POST /chat
AI powered reservation chatbot.

**Request:**
```json
{
    "session_id": "user_1",
    "message": "I want to book a table for 4 on December 25th at 7 PM"
}
```

**Response:**
```json
{
    "answer": "Your table has been booked! Reference number: 89233",
    "session_id": "user_1",
    "history_length": 2
}
```

### POST /book
Direct booking endpoint.

**Request:**
```json
{
    "customer_name": "Ahmed",
    "date": "2026-12-25",
    "time": "7:00 PM",
    "people": 4,
    "customer_phone": "555-1234"
}
```

**Response:**
```json
{
    "success": true,
    "reference": 97898
}
```

### POST /cancel
Cancels a reservation by reference number.

**Request:**
```json
{
    "reference": 97898
}
```

### POST /update
Updates an existing reservation.

**Request:**
```json
{
    "reference": 97898,
    "new_time": "8:00 PM"
}
```

### POST /check
Checks availability for a specific date and time.

**Request:**
```json
{
    "date": "2026-12-25",
    "time": "7:00 PM",
    "people": 4
}
```

### GET /reservations
Returns all confirmed reservations.
```
GET /reservations
GET /reservations?date=2026-12-25
```
## Database Schema

```sql
CREATE TABLE reservations (
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

CREATE TABLE restaurant_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    max_capacity INTEGER DEFAULT 50,
    opening_time TEXT DEFAULT '12:00',
    closing_time TEXT DEFAULT '23:00',
    slot_duration INTEGER DEFAULT 90
)
```

## Validation Rules
```
Time validation:
→ Must be within opening hours
→ Last booking = closing time minus slot duration (90 mins)
→ Default last booking: 21:30
Date validation:
→ Must be in the future
→ Format: YYYY-MM-DD
Capacity validation:
→ Maximum 50 people per time slot
→ Counts all overlapping bookings
Time formats accepted:
→ 7:00 PM, 7 PM, 19:00, 7pm, 7.00 PM
```
## Restaurant Configuration
```
Default settings stored in database:
max_capacity:  50 people
opening_time:  12:00
closing_time:  23:00
slot_duration: 90 minutes
```
## Soft Delete
```
Cancellations change status to cancelled — records never deleted:
confirmed  →  active booking
cancelled  →  cancelled booking (preserved for history)
```
## Environment Variables
```
API_KEY=your_groq_api_key
```

## Notes

- Never commit your .env file to GitHub
- Database created automatically on first run
- All times stored in HH:MM 24 hour format
- Conflict checking uses slot duration window