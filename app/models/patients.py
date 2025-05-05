from pydantic import BaseModel, Field
from typing import Optional, List 


class Patient(BaseModel):
    id: str
    username: str
    firstname: str
    lastname: str
    email: str
    connections: Optional[list] = []
    assigned_routines: Optional[list] = []
    imageUrl: Optional[str] = None
    streak: Optional[int] = 0
    expoPushToken: Optional[str] = None

class Exercises(BaseModel):
    id: str
    reps: int
    hold: int
    sets: int
    frequency: int
    description: str
    thumbnail_url: str
    video_url: str
    title: str
    category: str
    subcategory: str

class Routines(BaseModel):
    id: str
    name: str
    imageurl: str

class CompletedExercise(BaseModel):
    _id: str
    title: str
    date: str

class CompletedRoutine(BaseModel):
    _id: str
    name: str
    date: str

class CompletionLog(BaseModel):
    id: str = Field(..., alias="_id")
    completed_exercises: Optional[List[CompletedExercise]] = []
    completed_routines: Optional[List[CompletedRoutine]] = []
