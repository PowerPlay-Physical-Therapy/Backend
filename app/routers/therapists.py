from fastapi import HTTPException, APIRouter
from app.database import get_database
from app.models.therapists import Therapist
from pymongo.errors import PyMongoError
from bson import ObjectId

from dotenv import load_dotenv
import os
import boto3 

collection = get_database()["Therapists"]
routineCollection = get_database()["Routines"]
exerciseCollection = get_database()["Exercises"]

router = APIRouter(prefix="/therapist", tags=["Therapists"])


AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY_ID")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
S3_REGION = os.getenv("AWS_REGION")

s3_client = boto3.client(
    "s3"
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
    

@router.post("/upload_custom_video/")
def upload_custom_video(exercise_id: str, filename: str):
    try:
        exercise = exerciseCollection.find_one({"id": ObjectId(exercise_id)})
        if exercise:
            s3_key = f"custom_videos/{filename}"

            presigned_url = s3_client.generate_presigned_url(
                "put_object",
                Params={"Bucket": S3_BUCKET_NAME, "Key": s3_key, "ContentType": "video/mp4"},
                ExpiresIn=600
            )

            video_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{s3_key}"

            exerciseCollection.update_one(
                {"_id": ObjectId(exercise_id)},
                {"$set": {"video_url": video_url}}
            )
            return {"presigned_url": presigned_url, "video_url": video_url}

        else:
            # Item not found
            raise HTTPException(status_code=404, detail="Exercise not found")
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database update failed")
