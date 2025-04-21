from fastapi import HTTPException, APIRouter, Body
from app.database import get_database
from app.models.therapists import Therapist
from pymongo.errors import PyMongoError
from bson import ObjectId
from app.routers.common import get_routine_by_id, get_exercise_by_id, create_routine
from typing import Union, List
import logging
from dotenv import load_dotenv
import os
import boto3 

load_dotenv()

collection = get_database()["Therapists"]
routineCollection = get_database()["Routines"]
exerciseCollection = get_database()["Exercises"]

router = APIRouter(prefix="/therapist", tags=["Therapists"])


AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_REGION = os.getenv("AWS_REGION")

s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=S3_REGION
)

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


@router.post("/create_therapist", response_model=str, status_code=201)
def create_new_therapist(user: Therapist):
    try:
        user_dict = user.model_dump(by_alias=True, exclude=["id"])
        user_dict["_id"] = user.id
        user_dict["connections"] = []
        user_dict["custom_routines"] = []

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
        return convert_object_ids_to_strings(therapist)
    else:
        raise HTTPException(status_code=404, detail="Therapist not found")

@router.get("/get_therapist_by_email/")
def get_therapist_by_email(email: str):
    try:
        therapist = collection.find_one({"email": email})
        if therapist:
            therapist["_id"] = str(therapist["_id"])  # Convert ObjectId to string if needed
            return convert_object_ids_to_strings(therapist)
        else:
            raise HTTPException(status_code=404, detail="Therapist not found with provided email")
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database query failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail="An unexpected error occurred")

@router.put("/update_therapist/{therapist_username}")
def update_therapist_by_username(therapist_username: str, user: Therapist):
    try:
        result = collection.find_one({"username": therapist_username})
        if result:
            user_dict = user.model_dump(by_alias=True, exclude=["id"])
            update_fields = {
                "username": user_dict["username"],
                "imageUrl": user_dict.get("imageUrl"),
            }
            updated_item = collection.update_one(
                {"username": therapist_username},
                {"$set": update_fields}
            )
            if updated_item.modified_count == 1:
                return {"message": "Therapist updated successfully!"}
            else:
                raise HTTPException(status_code=400, detail="Failed to update item")
        else:
            raise HTTPException(status_code=404, detail="Item not found")
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database update failed")
    
    
@router.post("/create_exercise")
def create_exercise(exercises: Union[dict, List[dict]] = Body(...)):
    try:
        if isinstance(exercises, dict):
            exercises = [exercises]

        inserted_ids = []
        for exercise in exercises:
            if "_id" in exercise and exercise["_id"]:
                exercise["_id"] = ObjectId(exercise["_id"])
            inserted = exerciseCollection.insert_one(exercise)
            inserted_ids.append(str(inserted.inserted_id))

        if len(inserted_ids) == 1:
            return { "_id": inserted_ids[0] }
        return {
            "message": f"{len(inserted_ids)} exercise(s) created successfully!",
            "exercise_ids": inserted_ids
        }

    except PyMongoError as e:
        print(f"Database Insertion Error: {e}")
        raise HTTPException(status_code=500, detail="Database insertion failed")
    except Exception as e:
        print(f"Unexpected Error: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
    

@router.get("/get_custom_routines/{therapist_id}")
def get_custom_routines(therapist_id: str):
    therapist = collection.find_one({"_id": therapist_id})
    if therapist:
        routine_ids = [{"_id": str(routineID["_id"])} for routineID in therapist.get("custom_routines", [])]
        routines = [get_routine_by_id(routine["_id"]) for routine in routine_ids]
        for routine in routines:
            exercise_ids = [exercise["_id"] for exercise in routine.get("exercises", [])]
            routine["exercises"] = [get_exercise_by_id(exercise_id) for exercise_id in exercise_ids]
        return routines
    else:
        raise HTTPException(status_code=404, detail="No Such Therapist")

@router.put("/update_custom_routines/{therapist_id}/{routine_id}")
def update_custom_routines(therapist_id: str, routine_id: str):
    try:
        therapist = collection.find_one({"_id": therapist_id})

        if therapist:
            updated_item = collection.update_one(
                {"_id": therapist_id},
                {"$addToSet": {"custom_routines": {"_id": ObjectId(routine_id)}}}
            )

            if updated_item.modified_count == 1:
                return {"message": "Custom Routine updated successfully!"}
            else:
                raise HTTPException(
                    status_code=400, detail="Failed to add routine")
        else:
            # Item not found
            raise HTTPException(status_code=404, detail="Therapist not found")
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database update failed")
    