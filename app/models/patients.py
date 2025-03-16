from pydantic import BaseModel, Field
from bson import ObjectId


class Patient(BaseModel):
    id: str
    username: str
    firstname: str
    lastname: str
    email: str

class Exercises(BaseModel):
    id: str
    reps: int
    hold: int
    sets: int
    frequency: int
    description: str
    thumbnail_ur: str
    video_url: str
    title: str
    category: str
    subcategory: str

class Routines(BaseModel):
    id: str
    name: str
    imageurl: str