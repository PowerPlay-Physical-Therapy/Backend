from fastapi import HTTPException, APIRouter
from app.database import get_database
from app.models.patients import Patient, Routine
from pymongo.errors import PyMongoError
from bson import ObjectId

patientCollection = get_database()["Patients"]
exerciseCollection = get_database()["Exercises"]
routineCollection = get_database()["Routines"]
routine_collection = get_database()["Routine"]

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
    

    



@router.get("/get_patient_routine/")
def get_patient_routine_by_id(routine_id: str):
    collection_response = routine_collection.find_one({"_id": ObjectId(routine_id)})
    if collection_response:
        routine = collection_response
        print(f"\n\nRoutine Found: {routine}\n\n")
        return routine
    else:
        raise HTTPException(status_code=404, detail="Exercise not found")
    

    



@router.get("/get_patient_routine/")
def get_patient_routine_by_id(routine_id: str):
    collection_response = routine_collection.find_one({"_id": ObjectId(routine_id)})
    if collection_response:
        routine = collection_response
        print(f"\n\nRoutine Found: {routine}\n\n")
        return routine
    else:
        raise HTTPException(status_code=404, detail="Routine not found")
    

@router.put("/add_routine/{patient_id}")
def add_routine_to_patient(patient_id: str, routine_id: str):
    try:
        result = routine_collection.find_one({"id": patient_id})
        if result:
            updated_item = collection.update_one(
                {"_id": patient_id},
                {"$push": {"assigned_routines" : routine_id}}
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