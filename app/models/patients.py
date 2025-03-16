from pydantic import BaseModel, Field
from bson import ObjectId


class Patient(BaseModel):
    id: str
    username: str
    firstname: str
    lastname: str
    email: str

class Routine(BaseModel):
    id: str
    name: str
    imageurl: str