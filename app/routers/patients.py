from fastapi import HTTPException, APIRouter
from app.database import get_database
from app.models.patients import Patient
from pymongo.errors import PyMongoError
from bson import ObjectId

collection = get_database()["Patients"]

router = APIRouter(prefix="/patient", tags=["Patients"])

@router.post("/create_patient", response_model=str, status_code=201)
def create_new_patient(user: Patient):
    try:
        user_dict = user.model_dump(by_alias=True, exclude=["id"])
        user_dict["_id"] = user.id
        user_dict["connections"] = []
        user_dict["assigned_routines"] = []

        database_response = collection.insert_one(user_dict)
        print(f"\n\nNew Patient Added With ID : {database_response.inserted_id}\n\n")
        return database_response.inserted_id

    except PyMongoError as e:
        print(f"Database Insertion Error: {e}")
        raise HTTPException(status_code=500, detail="Database insertion failed")
    
    except Exception as e:
        print(f"Unexpected Error: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.get("/get_patient/{therapist_username}")
def get_patient_by_id(patient_id: str):
    collection_response = collection.find_one({"_id": patient_id})
    if collection_response:
        patient = collection_response
        print(f"\n\nPatient Found: {patient}\n\n")
        return patient
    else:
        raise HTTPException(status_code=404, detail="Patient not found")
    
@router.put("/update_patient/")
def update_patient_by_id(patient_username: str, user: Patient):
    try:
        result = collection.find_one({"username": patient_username})
        if result:
            user_dict = user.model_dump(by_alias=True, exclude=["id"])
            updated_item = collection.update_one(
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