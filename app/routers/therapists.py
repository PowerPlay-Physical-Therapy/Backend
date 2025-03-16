from fastapi import HTTPException, APIRouter
from app.database import get_database
from app.models.therapists import Therapist
from pymongo.errors import PyMongoError

collection = get_database()["Therapists"]

router = APIRouter(prefix="/therapist", tags=["Therapists"])


@router.post("/create_therapist", response_model=str, status_code=201)
def create_new_therapist(user: Therapist):
    try:
        user_dict = user.model_dump(by_alias=True, exclude=["id"])
        user_dict["_id"] = user.id
        user_dict["connections"] = []
        database_response = collection.insert_one(user_dict)
        
        print(
            f"\n\nNew Therapist Added With ID : {database_response.inserted_id}\n\n")
        return database_response.inserted_id

    except PyMongoError as e:
        print(f"Database Insertion Error: {e}")
        raise HTTPException(
            status_code=500, detail="Database insertion failed")

    except Exception as e:
        print(f"Unexpected Error: {e}")
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred")


@router.get("/get_therapist/")
def get_therapist_by_id(therapist_id: str):
    collection_response = collection.find_one({"_id": therapist_id})
    if collection_response:
        therapist = collection_response
        print(f"\n\nTherapist Found: {therapist}\n\n")
        return therapist
    else:
        raise HTTPException(status_code=404, detail="Therapist not found")


@router.put("/update_therapist/{therapist_username}")
def update_patient_by_id(therapist_username: str, user: Therapist):
    try:
        result = collection.find_one({"username": therapist_username})
        if result:
            user_dict = user.model_dump(by_alias=True, exclude=["id"])
            updated_item = collection.update_one(
                {"username" : therapist_username},
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
    
