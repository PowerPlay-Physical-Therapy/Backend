from pydantic import BaseModel, Field
from typing import Optional, Literal

class Therapist(BaseModel):
    id: str
    username: str
    firstname: str
    lastname: str
    email: str
    imageUrl: Optional[str] = None

class ConnectionBase(BaseModel):
    patient_id: str  # or ObjectId if you're using a custom field
    therapist_id: str
    status: Literal['pending', 'accepted'] = 'pending'
