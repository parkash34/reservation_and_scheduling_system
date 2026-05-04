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

class CheckAvailablilit(BaseModel):
    date: str
    time: str
    people: int


