from collections import defaultdict
from fastapi import HTTPException, APIRouter
from pymongo.errors import PyMongoError
from app.database import get_database
from bson import ObjectId

patientCollection = get_database()["Patients"]
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
    print(f"\n\nExercise Found: {exercise}\n\n")

    # Convert the ObjectId to a string
    exercise["_id"] = str(exercise["_id"])
    if exercise is not None:
        return exercise
    else:
        raise HTTPException(status_code=404, detail="Exercise not found")

# fetch routines to home page
@router.get("/get_routine/{routine_id}")
def get_routine_by_id(routine_id: str):
    routine = routineCollection.find_one({"_id": ObjectId(routine_id)})
    if routine:
        routine["_id"] = str(routine["_id"])

        exercise_ids = [str(exercise["_id"]) for exercise in routine.get("exercises", [])]
        exercises = exerciseCollection.find({"_id": {"$in": [ObjectId(id) for id in exercise_ids]}})
        routine["exercises"] = list(exercises)
        print(f"\n\nRoutine Found: {routine}\n\n")
        return routine
    else:
        raise HTTPException(status_code=404, detail="Routine not found")
    
# adding assigned routines to patients
@router.put("/add_routine/{patient_id}/{routine_id}")
def add_routine_to_patient(patient_id: str, routine_id: str):
    try:
        patient = patientCollection.find_one({"_id": ObjectId(patient_id)})

        if patient:
            updated_item = patientCollection.update_one(
                {"_id": ObjectId(patient_id)},
                {"$addToSet": {"assigned_routines" : ObjectId(routine_id)}}
            )

            if updated_item.modified_count == 1:
                return {"message": "Routine updated successfully!"}
            else:
                raise HTTPException(status_code=400, detail="Failed to add routine")
        else:
            # Item not found
            raise HTTPException(status_code=404, detail="Patient not found")
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database update failed")
