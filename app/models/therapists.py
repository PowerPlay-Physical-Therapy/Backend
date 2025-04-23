from pydantic import BaseModel, Field
from typing import Optional, Literal

class Therapist(BaseModel):
    id: str
    username: str
    firstname: str
    lastname: str
    email: str
    imageUrl: Optional[str] = None
    favorites: Optional[list[str]] = []

class ConnectionBase(BaseModel):
    patient_id: str
    therapist_id: str
    status: Optional[Literal['pending', 'accepted']] = 'pending'
    diagnosis: Optional[str] = ""
    notes: Optional[str] = ""

