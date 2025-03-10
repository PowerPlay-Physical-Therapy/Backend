from pydantic import BaseModel, Field
# from bson import ObjectId

class Patient(BaseModel):
    id: str
    username: str
    firstname: str
    lastname: str
    email: str
