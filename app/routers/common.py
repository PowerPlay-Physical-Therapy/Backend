from collections import defaultdict
from fastapi import HTTPException, APIRouter, UploadFile, status
from pymongo.errors import PyMongoError
from app.database import get_database
from bson import ObjectId
from uuid import uuid4
from loguru import logger

patientCollection = get_database()["Patients"]
therapistCollection = get_database()["Therapists"]
exerciseCollection = get_database()["Exercises"]
routineCollection = get_database()["Routines"]

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

        exercise_ids = [{"_id":str(exercise["_id"])} for exercise in routine.get("exercises", [])]
        # exercises = exerciseCollection.find({"_id": {"$in": [ObjectId(id) for id in exercise_ids]}})
        # exercises = [str(exercise["_id"]) for exercise in exercises]
        routine["exercises"] = list(exercise_ids)
        # print(f"\n\nRoutine Found: {routine}\n\n")
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
