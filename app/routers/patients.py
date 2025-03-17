from fastapi import HTTPException, APIRouter
from app.database import get_database
from app.models.patients import Patient
from pymongo.errors import PyMongoError
from bson import ObjectId
from app.routers.common import get_routine_by_id, get_exercise_by_id, create_routine

patientCollection = get_database()["Patients"]

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


@router.get("/get_patient/")
def get_patient_by_id(patient_id: str):
    collection_response = patientCollection.find_one({"_id": patient_id})
    if collection_response:
        patient = collection_response
        print(f"\n\nPatient Found: {patient}\n\n")
        return patient
    else:
        raise HTTPException(status_code=404, detail="Patient not found")
    
@router.put("/update_patient/{patient_username}")
def update_patient_by_id(patient_username: str, user: Patient):
    try:
        result = patientCollection.find_one({"username": patient_username})
        if result:
            user_dict = user.model_dump(by_alias=True, exclude=["id"])
            updated_item = patientCollection.update_one(
                {"username": patient_username},
                {"$set": {"username" : user_dict["username"]}}
            )
            if updated_item.modified_count == 1:
                return {"message": "Item updated successfully!"}
            else:
                raise HTTPException(status_code=400, detail="Failed to update item")
        else:
            # Item not found
            raise HTTPException(status_code=404, detail="Item not found")
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database update failed")
    

@router.put("/update_assigned_routines/{patient_id}/{routine_id}")
def update_assigned_routines(patient_id: str, routine_id: str):
    try:
        patient = patientCollection.find_one({"_id": patient_id})

        if patient:
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