from collections import defaultdict
from fastapi import HTTPException, APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from pymongo.errors import PyMongoError
from app.database import get_database
from bson import ObjectId

from datetime import datetime, timezone

patientCollection = get_database()["Patients"]
therapistCollection = get_database()["Therapists"]
exerciseCollection = get_database()["Exercises"]
routineCollection = get_database()["Routines"]
messageCollection = get_database()["Messages"]

router = APIRouter( tags=["Common"])

@router.get("/get_explore_collection")
def get_explore_collection():

    exercises = exerciseCollection.find()
    exercise_list = []
    for exercise in exercises:
        exercise["_id"] = str(exercise["_id"])
        exercise_list.append(exercise)

    def modify_exercises(exercise_list):
        transformed = defaultdict(lambda: defaultdict(list))
        for exercise in exercise_list:
            category = exercise["category"]
            subcategory = exercise["subcategory"]
            transformed[category][subcategory].append({
                "_id": {"$oid": exercise["_id"]},
                "reps": exercise["reps"],
                "hold": exercise["hold"],
                "sets": exercise["sets"],
                "frequency": exercise["frequency"],
                "description": exercise["description"],
                "thumbnail_url": exercise["thumbnail_url"],
                "video_url": exercise["video_url"],
                "name": exercise["title"]
            })
        result = []
        for category, subcategories in transformed.items():
            result.append({
                "title": category,
                "subcategory": [
                    {"subtitle": subcat, "exercises": exercises}
                    for subcat, exercises in subcategories.items()
                ]
            })
        return result

    return modify_exercises(exercise_list)


@router.get("/get_exercise/{exercise_id}")
def get_exercise_by_id(exercise_id: str):
    exercise = exerciseCollection.find_one({"_id": ObjectId(exercise_id)})
    # print(f"\n\nExercise Found: {exercise}\n\n")

    # Convert the ObjectId to a string
    exercise["_id"] = str(exercise["_id"])
    if exercise is not None:
        return exercise
    else:
        raise HTTPException(status_code=404, detail="Exercise not found")
    

# fetching routine by id
@router.get("/get_routine/{routine_id}")
def get_routine_by_id(routine_id: str):
    routine = routineCollection.find_one({"_id": ObjectId(routine_id)})

    if routine:
        routine["_id"] = str(routine["_id"])

        # Extract exercise ObjectIds
        exercise_ids = [exercise["_id"]
                        for exercise in routine.get("exercises", [])]

        # Fetch full exercise documents
        exercises = list(exerciseCollection.find(
            {"_id": {"$in": exercise_ids}}))

        # Convert ObjectId to string for each exercise
        for exercise in exercises:
            exercise["_id"] = str(exercise["_id"])

        # Attach full exercises to routine
        routine["exercises"] = exercises

        return routine
    else:
        raise HTTPException(status_code=404, detail="Routine not found")
    
@router.post("/create_routine")
def create_routine(routine: dict):
    try:
        routine_id = routineCollection.insert_one(routine).inserted_id
        return {"message": "Routine created successfully!", "routine_id": str(routine_id)}
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database update failed")


def convert_message(doc):
    doc["_id"] = str(doc["_id"])
    doc["timestamp"] = doc["timestamp"]
    return doc


@router.get("/messages/{user1}/{user2}")
def get_messages(user1: str, user2: str):
    # Query for all messages between user1 and user2
    cursor = messageCollection.find({
        "$or": [
            {"sender_id": user1, "receiver_id": user2},
            {"sender_id": user2, "receiver_id": user1}
        ]
    }).sort("timestamp", 1)

    messages = []
    for msg in cursor:
        messages.append(convert_message(msg))

    return JSONResponse(content=jsonable_encoder(messages))

@router.put("/message/{user1}/{user2}")
async def update_messages(user1: str, user2: str, request: Request):
    data = await request.json()
    message = data.get("message")
    type = data.get("type")
    tempObj: dict = {
        "sender_id": user1,
        "receiver_id": user2,
        "type": type,
        "read": False,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "message": message}
    
    try: 
        message_id = messageCollection.insert_one(tempObj)
        return {"message": "Message sent successfully", "message_id" : str(message_id.inserted_id)}
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database update failed")

# @router.websocket("/chat")
# def chat(websocket):