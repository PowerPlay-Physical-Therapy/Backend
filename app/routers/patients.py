from fastapi import HTTPException, APIRouter
from app.database import get_database
from app.models.patients import Patient
from pymongo.errors import PyMongoError
from bson import ObjectId
from app.routers.common import get_routine_by_id, get_exercise_by_id, create_routine
from datetime import datetime
import random

patientCollection = get_database()["Patients"]
completionCollection = get_database()["PatientHistory"]

router = APIRouter(prefix="/patient", tags=["Patients"])

@router.post("/create_patient", response_model=str, status_code=201)
def create_new_patient(user: Patient):
    try:
        user_dict = user.model_dump(by_alias=True, exclude=["id"])
        user_dict["_id"] = user.id
        user_dict["connections"] = []
        user_dict["assigned_routines"] = []

        database_response = patientCollection.insert_one(user_dict)
        print(f"\n\nNew Patient Added With ID : {database_response.inserted_id}\n\n")
        return database_response.inserted_id

    except PyMongoError as e:
        print(f"Database Insertion Error: {e}")
        raise HTTPException(status_code=500, detail="Database insertion failed")
    
    except Exception as e:
        print(f"Unexpected Error: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


# support function
def convert_object_ids_to_strings(data):
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "_id":
                if isinstance(value, dict) and "$oid" in value:
                    # Convert MongoDB ObjectId to string
                    data[key] = value["$oid"]
                else:
                    data[key] = str(value)  # Ensure all _id values are strings
            else:
                data[key] = convert_object_ids_to_strings(
                    value)  # Recursively process other fields
    elif isinstance(data, list):
        # Recursively process lists
        return [convert_object_ids_to_strings(item) for item in data]
    return data

@router.get("/get_patient/{patient_id}")
def get_patient_by_id(patient_id: str):
    print("Looking for patient with ID:", patient_id)

    # DEBUG: print one sample patient
    sample = patientCollection.find_one()
    print("Sample document from Patients:", sample)

    # Check if the document with matching ID exists
    patient = patientCollection.find_one({"_id": patient_id})
    print("Patient query result:", patient)

    if patient:
        return convert_object_ids_to_strings(patient)
    else:
        raise HTTPException(status_code=404, detail="Patient not found")

@router.put("/update_assigned_routines/{patient_id}/{routine_id}")
def update_assigned_routines(patient_id: str, routine_id: str):
    try:
        patient = patientCollection.find_one({"_id": patient_id})

        if patient:
            # Check if the routine already exists in assigned_routines
            existing_routine = patientCollection.find_one(
                {"_id": patient_id, "assigned_routines._id": ObjectId(routine_id)}
            )
            if existing_routine:
                return {"message": "Routine already assigned to this patient!"}
            
            updated_item = patientCollection.update_one(
                {"_id": patient_id},
                {"$addToSet": {"assigned_routines": {"_id": ObjectId(routine_id)}}}
            )

            if updated_item.modified_count == 1:
                return {"message": "Assign Routine updated successfully!"}
            else:
                raise HTTPException(
                    status_code=400, detail="Failed to add routine")
        else:
            # Item not found
            raise HTTPException(status_code=404, detail="Patient not found")
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database update failed")

# adding assigned routines to patients
@router.post("/add_explore_routine/{patient_id}")
def add_explore_routine(patient_id:str, routine: dict):
    try : 
        for exercise in routine.get("exercises", []):
            if isinstance(exercise["_id"], str):
                exercise["_id"] = ObjectId(exercise["_id"])
                
        routine_id = create_routine(routine).get("routine_id")
        print(f"\n\nRoutine ID: {routine_id}\n\n")
        update_assigned_routines(patient_id, routine_id)
        return {"message": "Routine added successfully!"}
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database update failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.get("/get_assigned_routines/{patient_id}")
def get_assigned_routines(patient_id: str):
    patient = patientCollection.find_one({"_id": patient_id})
    if patient:
        routine_ids = [{"_id": str(routineID["_id"])} for routineID in patient.get("assigned_routines", [])]
        routines = [get_routine_by_id(routine["_id"]) for routine in routine_ids]
        for routine in routines:
            exercise_ids = [exercise["_id"] for exercise in routine.get("exercises", [])]
            routine["exercises"] = [get_exercise_by_id(exercise_id) for exercise_id in exercise_ids]
        return routines
    else:
        raise HTTPException(status_code=404, detail="No Such Patient")    


@router.get("/get_connections/{patient_id}")
def get_connections(patient_id: str):
    patient = patientCollection.find_one({"_id": patient_id})
    if patient:
        connections = patient.get("connections", [])
        print(f"\n\nConnections Found: {connections}\n\n")
        return connections
    else:
        raise HTTPException(status_code=404, detail="No Therapist Found for this Patient")
    
@router.get("/get_patient_by_email/{email}")
def get_patient_by_email(email: str):
    try:
        patient = patientCollection.find_one({"email": email})
        if patient:
            patient["_id"] = str(patient["_id"])
            return convert_object_ids_to_strings(patient)
        else:
            raise HTTPException(status_code=404, detail="Patient not found with provided email")
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database query failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail="An unexpected error occurred")

@router.put("/update_patient/{patient_username}")
def update_patient_by_username(patient_username: str, user: Patient):
    try:
        result = patientCollection.find_one({"username": patient_username})
        if result:
            user_dict = user.model_dump(by_alias=True, exclude=["id"])
            update_fields = {
                "username": user_dict.get("username"),
                "imageUrl": user_dict.get("imageUrl"),
            }
            updated_item = patientCollection.update_one(
                {"username": patient_username},
                {"$set": update_fields}
            )
            if updated_item.modified_count == 1:
                return {"message": "Item updated successfully!"}
            else:
                return {"message": "No changes made to the item."}
        else:
            raise HTTPException(status_code=404, detail="Item not found")
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database update failed")
    
def validate_log(user_id: str):
    if not completionCollection.find_one({"_id": user_id}):
        completionCollection.insert_one({
            "_id": user_id,
            "completed_routines": [],
            "completed_exercises": []
        })

@router.put("/complete_routine/{user_id}/{routine_id}")
def mark_routine_complete(user_id: str, routine_id: str, name: str = ""):
    try:
        validate_log(user_id)
        routine_entry = {
            "_id": routine_id,
            "name": name,
            "date": datetime.utcnow().isoformat()
        }
        completionCollection.update_one(
            {"_id": user_id},
            {"$addToSet": {"completed_routines": routine_entry}}
        )
        return {"message": "Routine marked as completed."}
    except PyMongoError:
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/complete_exercise/{user_id}/{exercise_id}")
def mark_exercise_complete(user_id: str, exercise_id: str, title: str = ""):
    try:
        validate_log(user_id)
        exercise_entry = {
            "_id": exercise_id,
            "title": title,
            "date": datetime.utcnow().isoformat()
        }
        completionCollection.update_one(
            {"_id": user_id},
            {"$addToSet": {"completed_exercises": exercise_entry}}
        )
        return {"message": "Exercise marked as completed."}
    except PyMongoError:
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/get_completed_exercises/{patient_id}")
def get_completed_exercises(patient_id: str):
    try:
        logs = list(logCollection.find({
            "user_id": patient_id,
            "type": "exercise"
        }))
        completed = []
        for log in logs:
            exercise = exerciseCollection.find_one({"_id": ObjectId(log["item_id"])})
            if exercise:
                exercise["_id"] = str(exercise["_id"])
                completed.append({
                    "date": log.get("date"),
                    "title": exercise.get("title"),
                    "category": exercise.get("category"),
                    "subcategory": exercise.get("subcategory")
                })
        return completed
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database query failed")

@router.get("/get_completed_routines/{patient_id}")
def get_completed_routines(patient_id: str):
    try:
        logs = list(logCollection.find({
            "user_id": patient_id,
            "type": "routine"
        }))
        completed = []
        for log in logs:
            routine = routineCollection.find_one({"_id": ObjectId(log["item_id"])})
            if routine:
                routine["_id"] = str(routine["_id"])
                completed.append({
                    "date": log.get("date"),
                    "name": routine.get("name"),
                })
        return completed
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database query failed")

@router.get("/get_progress/{patient_id}")
def get_progress(patient_id: str):
    return {"patient_id": patient_id, "progress": random.randint(0, 100)}