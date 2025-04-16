from fastapi import HTTPException, APIRouter, Body
from app.database import get_database
from app.models.therapists import Therapist
from pymongo.errors import PyMongoError
from bson import ObjectId
from app.routers.common import get_routine_by_id, get_exercise_by_id, create_routine
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
    

# @router.post("/upload_custom_video/")
# def upload_custom_video(exercise_id: str, filename: str, content_type: str = "video/mp4"):
#     try:
#         exercise = exerciseCollection.find_one({"_id": ObjectId(exercise_id)})
#         if exercise:
#             s3_key = f"custom_videos/{filename}"

#             presigned_url = s3_client.generate_presigned_url(
#                 "put_object",
#                 Params={"Bucket": S3_BUCKET_NAME, "Key": s3_key, "ContentType": content_type},
#                 ExpiresIn=600
#             )

#             video_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{s3_key}"

#             exerciseCollection.update_one(
#                 {"_id": ObjectId(exercise_id)},
#                 {"$set": {"video_url": video_url}}
#             )
#             return {"presigned_url": presigned_url, "video_url": video_url}

#         else:
#             # Item not found
#             raise HTTPException(status_code=404, detail="Exercise not found")
#     except PyMongoError as e:
#         raise HTTPException(status_code=500, detail="Database update failed")


@router.post("/create_exercise")
def create_exercise(exercise: dict = Body(...)):
    try:
        # If _id is provided, convert to ObjectId and update instead
        if "_id" in exercise and exercise["_id"]:
            exercise["_id"] = ObjectId(exercise["_id"])
        
        inserted = exerciseCollection.insert_one(exercise)
        return {
            "message": "Exercise created successfully!",
            "exercise_id": str(inserted.inserted_id)
        }

    except PyMongoError as e:
        print(f"Database Insertion Error: {e}")
        raise HTTPException(status_code=500, detail="Database insertion failed")
    except Exception as e:
        print(f"Unexpected Error: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")



@router.post("/add_custom_routine/{therapist_id}")
def add_custom_routine(therapist_id: str, routine: dict):
    """
    Endpoint for therapists to create and save custom routines.
    """
    try:
        # Ensure exercise IDs are in ObjectId format
        for exercise in routine.get("exercises", []):
            if isinstance(exercise["_id"], str):
                exercise["_id"] = ObjectId(exercise["_id"])


        # Save routine to database
        routine["therapist_id"] = ObjectId(therapist_id)  # Link to therapist
        routine_id = routineCollection.insert_one(routine).inserted_id


        return {"message": "Routine added successfully!", "routine_id": str(routine_id)}


    except PyMongoError:
        raise HTTPException(status_code=500, detail="Database update failed")
    except Exception:
        raise HTTPException(status_code=500, detail="An unexpected error occurred")




@router.get("/get_custom_routines/{therapist_id}")
def get_custom_routines(therapist_id: str):
    """
    Fetches all custom routines created by a specific therapist.
    """
    try:
        logging.info(f"Fetching routines for therapist_id: {therapist_id}")


        # Fetch therapist's document
        therapist = therapistCollection.find_one({"_id": therapist_id})


        if not therapist:
            raise HTTPException(status_code=404, detail="Therapist not found")


        # Extract routine IDs
        routine_ids = [routine["_id"]["$oid"] if isinstance(routine["_id"], dict) and "$oid" in routine["_id"] else str(routine["_id"])
                        for routine in therapist.get("custom_routines", [])]


        if not routine_ids:
            raise HTTPException(status_code=404, detail="No routines found for this therapist")


        # Fetch routines using extracted routine IDs
        routines = list(routineCollection.find({"_id": {"$in": [ObjectId(rid) for rid in routine_ids]}}))


        # Convert ObjectId fields to strings for JSON response
        for routine in routines:
            routine["_id"] = str(routine["_id"])


            # Convert exercise IDs to string
            for exercise in routine.get("exercises", []):
                exercise["_id"] = str(exercise["_id"])
                exercise_details = get_exercise_by_id(exercise["_id"])
                exercise.update(exercise_details)


        return routines


    except PyMongoError as e:
        logging.error(f"Database query failed: {e}")
        raise HTTPException(status_code=500, detail="Database query failed")


    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
