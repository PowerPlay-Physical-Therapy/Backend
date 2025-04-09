from pydantic import BaseModel, Field
from typing import Optional

class Therapist(BaseModel):
    id: str
    username: str
    firstname: str
    lastname: str
    email: str
    imageUrl: Optional[str] = None
