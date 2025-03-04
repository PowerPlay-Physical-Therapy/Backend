from fastapi import HTTPException, APIRouter
from database import get_database
from app.models.patients import Patient
from pymongo.errors import PyMongoError

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


@router.get("/get_patient/")
def get_patient_by_id(patient_id: str):
    collection_response = collection.find_one({"_id": patient_id})
    if collection_response:
        patient = collection_response
        print(f"\n\nPatient Found: {patient}\n\n")
        return patient
    else:
        raise HTTPException(status_code=404, detail="Patient not found")
