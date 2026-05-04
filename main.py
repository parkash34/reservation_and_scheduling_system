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

sessions = {}
db_manager = DatabaseManager("restaurant.db")


class BookingRequest(BaseModel):
    customer_name: str
    date: str
    time: str
    people: int
    customer_phone: str
    customer_email: str
    special_requirement: str

class CancelRequest(BaseModel):
    reference: str

class UpdateRequest(BaseModel):
    reference: str
    new_date: str
    new_time: str
    new_people: int

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
    
class CheckAvailablilit(BaseModel):
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
def check_table_availablility(date: str, time: str, people: str) -> dict:
    people = int(people)
    return db_manager.check_availability(date, time, people)

@tool
def book_table(customer_name: str, date: str, time: str , people: str, special_requirement: str = None) -> dict:
    people = int(people)
    return db_manager.book_with_validation(customer_name, date, time, people, None, None, special_requirement)

@tool
def get_my_reservation(reference: str) -> dict:
    reference = int(reference)
    return db_manager.get_reservation_by_reference(reference)

@tool
def find_reservations_by_name(name: str) -> dict:
    return db_manager.get_reservations_by_name(name)

@tool
def cancel_my_reservation(reference: str) -> dict:
    reference = int(reference)
    return db_manager.cancel_reservation(reference)

@tool
def update_my_reservation(reference: int, new_date: str, new_time: str, new_people: str=None ) -> dict:
    reference = int(reference)
    new_people = int(new_people)
    return db_manager.update_reservation(reference, new_date, new_time, new_people)



     
