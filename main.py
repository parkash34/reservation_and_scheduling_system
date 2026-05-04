import os
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel, field_validator
from typing import Optional
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from database import DatabaseManager


load_dotenv()

api_key = os.getenv("API_KEY")
if not api_key:
    raise ValueError("API KEY is missing in env file")

app = FastAPI()
sessions = {}
db_manager = DatabaseManager("restaurant.db")


class BookingRequest(BaseModel):
    customer_name: str
    date: str
    time: str
    people: int
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    special_requirement: Optional[str] = None

class CancelRequest(BaseModel):
    reference: int

class UpdateRequest(BaseModel):
    reference: int
    new_date: Optional[str] = None
    new_time: Optional[str] = None
    new_people: Optional[int] = None

class ChatMessage(BaseModel):
    session_id: str
    message: str

    @field_validator("session_id")
    @classmethod
    def session_id_is_missing(cls, v):
        if not v.strip():
            raise ValueError("Session ID is missing")
        return v
    
    @field_validator("message")
    @classmethod
    def message_is_empty(cls, v):
        if not v.strip():
            raise ValueError("Message is Empty")
        return v
    
class CheckAvailability(BaseModel):
    date: str
    time: str
    people: int

llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.2,
        max_tokens=500,
        api_key=api_key
    )

@tool
def check_table_availability(date: str, time: str, people: str) -> dict:
    """Checks if a table is available for a specific date, time and number of people.
    Use this BEFORE booking to verify availability.
    Date format must be YYYY-MM-DD like 2026-05-04.
    Time can be any format like 7 PM, 19:00 or 7:00 PM.
    People must be a number like 4."""
    people = int(people)
    return db_manager.check_availability(date, time, people)

@tool
def book_table(customer_name: str, date: str, time: str , people: str, special_requirement: str = None) -> dict:
    """Books a table at the restaurant for a customer.
    Use this AFTER checking availability.
    Requires customer name, date in YYYY-MM-DD format, time and number of people.
    Special requirement is optional — use for dietary needs or special occasions.
    Always check availability first before calling this tool."""
    people = int(people)
    return db_manager.book_with_validation(customer_name, date, time, people, None, None, special_requirement)

@tool
def get_my_reservation(reference: str) -> dict:
    """Retrieves reservation details by reference number.
    Use this when customer asks about their existing booking.
    Requires the reference number given at time of booking."""
    reference = int(reference)
    return db_manager.get_reservation_by_reference(reference)

@tool
def find_reservations_by_name(name: str) -> dict:
    """Finds all reservations for a customer by their name.
    Use this when customer provides their name and wants to see their bookings.
    Returns all confirmed reservations sorted by date and time."""
    return db_manager.get_reservations_by_name(name)

@tool
def cancel_my_reservation(reference: str) -> dict:
    """Cancels an existing reservation by reference number.
    Use this when customer wants to cancel their booking.
    Requires the reference number.
    Always confirm with customer before cancelling."""
    reference = int(reference)
    return db_manager.cancel_reservation(reference)

@tool
def update_my_reservation(reference: str, new_date: str = None, new_time: str= None, new_people: str= None ) -> dict:
    """Updates an existing reservation by reference number.
    Use this when customer wants to change their booking details.
    Only provide the fields that need to be changed.
    Reference number is required.
    New date format must be YYYY-MM-DD.
    New time can be any format like 7 PM or 19:00."""
    reference = int(reference)
    new_people = int(new_people) if new_people else None
    return db_manager.update_reservation(reference, new_date, new_time, new_people)


config = db_manager.get_config()

system_prompt = f"""You are Sofia, a reservation specialist for Bella Italia restaurant.
    You ONLY handle table bookings, cancellations, updates and reservation lookups.

    RESTAURANT INFORMATION:
    - Name: Bella Italia
    - Location: Astoria, New York
    - Phone: 123-456-7890
    - Opening Hours:{config['opening_time']} to {config['closing_time']}
    - Maximum capacity: {config["max_capacity"]}

    TOOL USAGE RULES:
    - Always call check_table_availability() before booking
    - Always call book_table() to make a reservation
    - Always call get_my_reservation() when customer asks about their booking
    - Always call find_reservations_by_name() when customer gives their name
    - Always call cancel_my_reservation() to cancel a booking
    - Always call update_my_reservation() to modify a booking

    INFORMATION GATHERING RULES:
    - Never book without ALL of these: customer name, date, time, number of people
    - If any information is missing ask for it before proceeding
    - Always confirm details with customer before booking
    - Date must be in YYYY-MM-DD format — convert if customer says "tomorrow" or "next Friday"
    - Time can be any format — system handles conversion automatically

    BOOKING STEPS:
    1. GATHER — collect name, date, time, people count
    2. CONFIRM — repeat details back to customer
    3. CHECK — call check_table_availability()
    4. BOOK — call book_table() if available
    5. CONFIRM — give reference number to customer

    GUARDRAIL RULES:
    - Only handle reservation related questions
    - If asked about menu redirect politely
    - If asked unrelated questions redirect politely
    - Never make up availability — always use tools

    TONE:
    - Professional, warm and efficient
    - Always confirm bookings with reference number
    - If booking fails explain why clearly
    """

tools = [
    check_table_availability,
    book_table,
    get_my_reservation,
    find_reservations_by_name,
    cancel_my_reservation,
    update_my_reservation
]

agent = create_react_agent(llm, tools, prompt=system_prompt)

def get_session(session_id: str) -> list:
    if session_id not in sessions:
        sessions[session_id] = []

    return sessions[session_id]

@app.post("/chat")
def chat(message: ChatMessage):
    try:
        session_id = message.session_id
        query = message.message

        history = get_session(session_id)
        history.append(HumanMessage(content=query))

        result = agent.invoke({"messages": history})
        ai_message = result["messages"][-1]

        history.append(ai_message)

        return {
            "answer": ai_message.content,
            "session_id": session_id,
            "history_length": len(history)
        }

    except Exception as e:
        return {
            "answer": "Sorry I am having trouble right now. Please try again.",
            "error": str(e)
        }

@app.post("/book")
def booking(booking_request: BookingRequest):
    customer_name = booking_request.customer_name
    date = booking_request.date
    time = booking_request.time
    people = booking_request.people
    customer_phone = booking_request.customer_phone
    customer_email = booking_request.customer_email
    special_requirement = booking_request.special_requirement
    return db_manager.book_with_validation(customer_name,date,time,people,customer_phone,customer_email,special_requirement)


@app.post("/cancel")
def canceling(cancel_request: CancelRequest):
    reference = cancel_request.reference
    return db_manager.cancel_reservation(reference)


@app.post("/update")
def updating(update_request: UpdateRequest):
    reference = update_request.reference
    new_date = update_request.new_date
    new_time = update_request.new_time
    new_people = update_request.new_people
    return db_manager.update_reservation(reference, new_date, new_time, new_people)

@app.get("/reservations")
def getting_reservations(date: str= None):
    return db_manager.get_all_reservations(date)

@app.post("/check")
def checking(check_request: CheckAvailability):
    date = check_request.date
    time = check_request.time
    people = check_request.people
    
    return db_manager.check_availability(date,time,people)