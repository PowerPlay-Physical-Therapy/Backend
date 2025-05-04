from exponent_server_sdk import (
    DeviceNotRegisteredError,
    PushClient,
    PushMessage,
    PushServerError,
    PushTicketError,
)

import rollbar
import requests
from requests.exceptions import ConnectionError, HTTPError
from fastapi import HTTPException, APIRouter, Body
from app.database import get_database
from app.models.therapists import Therapist, ConnectionBase
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
connectionCollection = get_database()["Connections"]

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
                "username": user_dict.get("username"),
                "imageUrl": user_dict.get("imageUrl"),
                "expoPushToken": user_dict.get("expoPushToken"),
            }
            updated_item = collection.update_one(
                {"username": therapist_username},
                {"$set": update_fields}
            )
            if updated_item.modified_count == 1:
                return {"message": "Therapist updated successfully!"}
            else:
                return {"message": "No changes made to the therapist"}
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

@router.put("/add_custom_routines/{therapist_id}/{routine_id}")
def add_custom_routines(therapist_id: str, routine_id: str):
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
    

@router.put("/update_exercise/{exercise_id}")
async def update_exercise(exercise_id: str, updated_data: dict = Body(...)):
    try:
        existing = exerciseCollection.find_one({"_id": ObjectId(exercise_id)})
        
        if existing:
            updated_item = exerciseCollection.update_one(
                {"_id": ObjectId(exercise_id)},
                {"$set": updated_data}
            )
            return {"message": "Exercise updated", "matched": updated_item.matched_count}
        else:
            raise HTTPException(status_code=404, detail="Exercise not found")
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database update failed")

@router.put("/update_routine/{routine_id}")
async def update_routine(routine_id: str, updated_data: dict = Body(...)):
    try:
        existing = routineCollection.find_one({"_id": ObjectId(routine_id)})

        if not existing:
            raise HTTPException(status_code=404, detail="Routine not found")

        # Only store references to valid exercises
        if "exercises" in updated_data:
            exercise_refs = []

            for ex in updated_data["exercises"]:
                if "_id" in ex and ex["_id"]:
                    # Validate the exercise exists
                    ex_id = ObjectId(ex["_id"])
                    if not exerciseCollection.find_one({"_id": ex_id}):
                        raise HTTPException(status_code=404, detail=f"Exercise with _id {ex_id} not found")
                    # Just reference it
                    exercise_refs.append({"_id": ex_id})
                else:
                    # Only insert new exercise
                    inserted = exerciseCollection.insert_one(ex)
                    exercise_refs.append({"_id": inserted.inserted_id})

            updated_data["exercises"] = exercise_refs

        # Remove fields not wanted to update
        updated_data.pop("_id", None)

        updated_item = routineCollection.update_one(
            {"_id": ObjectId(routine_id)},
            {"$set": updated_data}
        )

        return {
            "message": "Routine updated",
            "matched_count": updated_item.matched_count,
            "modified_count": updated_item.modified_count
        }

    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database update failed")

@router.put("/update_favorites/{therapist_id}")
async def update_favorites(therapist_id: str, update_data: dict = Body(...)):
    try:
        # Validate required fields
        if "exerciseId" not in update_data:
            raise HTTPException(
                status_code=400, 
                detail="exerciseId is required"
            )
        
        exercise_id = update_data["exerciseId"]
            
        # Check if therapist exists
        therapist = collection.find_one({"_id": therapist_id})
        if not therapist:
            raise HTTPException(status_code=404, detail="Therapist not found")
            
        # Check if exercise exists
        exercise = exerciseCollection.find_one({"_id": ObjectId(exercise_id)})
        if not exercise:
            raise HTTPException(status_code=404, detail="Exercise not found")
        
        # Check if exercise is already in favorites
        is_favorited = exercise_id in therapist.get("favorites", [])
        
        if is_favorited:
            # Remove exercise ID from favorites
            result = collection.update_one(
                {"_id": therapist_id},
                {"$pull": {"favorites": exercise_id}}
            )
            action = "removed from"
        else:
            # Add exercise ID to favorites
            result = collection.update_one(
                {"_id": therapist_id},
                {"$addToSet": {"favorites": exercise_id}}
            )
            action = "added to"
            
        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to update favorites")
                
        return {
            "message": f"Successfully {action} favorites",
            "therapist_id": therapist_id,
            "exercise_id": exercise_id,
            "is_favorited": not is_favorited  # Return the new state
        }
        
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database operation failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/get_connection_details/{patient_id}/{therapist_id}")
def get_connection_details(patient_id: str, therapist_id: str):
    try:
        connection = connectionCollection.find_one({
            "patient_id": patient_id,
            "therapist_id": therapist_id
        })

        if not connection:
            raise HTTPException(status_code=404, detail="Connection not found")

        return {
            "diagnosis": connection.get("diagnosis", ""),
            "notes": connection.get("notes", "")
        }

    except Exception as e:
        print("Error fetching connection details:", str(e))
        raise HTTPException(status_code=500, detail="Error fetching connection details")

@router.put("/update_connection_details/{patient_id}/{therapist_id}")
def update_connection_details(
    patient_id: str,
    therapist_id: str,
    data: dict = Body(...)
):
    try:
        diagnosis = data.get("diagnosis", "")
        notes = data.get("notes", "")

        result = connectionCollection.update_one(
            {"patient_id": patient_id, "therapist_id": therapist_id},
            {"$set": {"diagnosis": diagnosis, "notes": notes}}
        )

        if result.modified_count == 1:
            return {"message": "Connection details updated"}
        else:
            raise HTTPException(status_code=404, detail="Connection not found or no change made")

    except Exception as e:
        print("Error updating connection details:", str(e))
        raise HTTPException(status_code=500, detail="Error updating connection details")

@router.post("/add_favorite/{therapist_id}/{exercise_id}")
def add_favorite_exercise(therapist_id: str, exercise_id: str):
    try:
        result = collection.update_one(
            {"_id": therapist_id},
            {"$addToSet": {"favorites": exercise_id}}
        )
        if result.modified_count == 1:
            return {"message": "Exercise added to favorites"}
        else:
            raise HTTPException(status_code=400, detail="Exercise already in favorites or therapist not found")
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database update failed")


@router.delete("/remove_favorite/{therapist_id}/{exercise_id}")
def remove_favorite_exercise(therapist_id: str, exercise_id: str):
    try:
        result = collection.update_one(
            {"_id": therapist_id},
            {"$pull": {"favorites": exercise_id}}
        )
        if result.modified_count == 1:
            return {"message": "Exercise removed from favorites"}
        else:
            raise HTTPException(status_code=400, detail="Exercise not in favorites or therapist not found")
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database update failed")

@router.get("/get_favorite_routines/{therapist_id}")
def get_favorite_routines(therapist_id: str):
    try:
        therapist = collection.find_one({"_id": therapist_id})
        if not therapist:
            raise HTTPException(status_code=404, detail="Therapist not found")

        favorite_ids = [ObjectId(rid) for rid in therapist.get("favorites", []) if rid]
        routines = list(routineCollection.find({"_id": {"$in": favorite_ids}}))

        for routine in routines:
            routine["_id"] = str(routine["_id"])
            exercise_ids = [ex["_id"] for ex in routine.get("exercises", [])]
            full_exercises = list(exerciseCollection.find({"_id": {"$in": exercise_ids}}))

            for ex in full_exercises:
                ex["_id"] = str(ex["_id"])
            routine["exercises"] = full_exercises

        print("Matching routine IDs:", favorite_ids)
        print("Routines found:", [r["_id"] for r in routines])
        return routines

    except PyMongoError:
        raise HTTPException(status_code=500, detail="Database query failed")
    except Exception as e:
        print("Error fetching favorites:", e)
        raise HTTPException(status_code=500, detail="Unexpected error")

@router.put("/toggle_favorite/{therapist_id}/{routine_id}")
def toggle_favorite_routine(therapist_id: str, routine_id: str):
    try:
        therapist = collection.find_one({"_id": therapist_id})
        if not therapist:
            raise HTTPException(status_code=404, detail="Therapist not found")

        favorites = therapist.get("favorites", [])

        if routine_id in favorites:
            # Remove from favorites
            result = collection.update_one(
                {"_id": therapist_id},
                {"$pull": {"favorites": routine_id}}
            )
            return {"message": "Routine removed from favorites"}
        else:
            # Add to favorites
            result = collection.update_one(
                {"_id": therapist_id},
                {"$addToSet": {"favorites": routine_id}}
            )
            return {"message": "Routine added to favorites"}

    except PyMongoError:
        raise HTTPException(status_code=500, detail="Database update failed")
    except Exception as e:
        print("Error toggling favorite:", str(e))
        raise HTTPException(status_code=500, detail="Unexpected error")
    
session = requests.Session()
session.headers.update(
    {
        "Authorization": f"Bearer {os.getenv('EXPO_TOKEN')}",
        "accept": "application/json",
        "accept-encoding": "gzip, deflate",
        "content-type": "application/json",
    }
)

@router.post("/send_push_message/{token}")
def send_push_message(token, message, extra=None):
    try:
        response = PushClient(session=session).publish(
            PushMessage(to=token,
                        body=message,
                        data=extra))
    except PushServerError as exc:
        # Encountered some likely formatting/validation error.
        rollbar.report_exc_info(
            extra_data={
                'token': token,
                'message': message,
                'extra': extra,
                'errors': exc.errors,
                'response_data': exc.response_data,
            })
        raise
    except (ConnectionError, HTTPError) as exc:
        # Encountered some Connection or HTTP error - retry a few times in
        # case it is transient.
        rollbar.report_exc_info(
            extra_data={'token': token, 'message': message, 'extra': extra})
        raise self.retry(exc=exc)

    try:
        # We got a response back, but we don't know whether it's an error yet.
        # This call raises errors so we can handle them with normal exception
        # flows.
        response.validate_response()
    except DeviceNotRegisteredError:
        # Mark the push token as inactive
        from notifications.models import PushToken
        PushToken.objects.filter(token=token).update(active=False)
    except PushTicketError as exc:
        # Encountered some other per-notification error.
        rollbar.report_exc_info(
            extra_data={
                'token': token,
                'message': message,
                'extra': extra,
                'push_response': exc.push_response._asdict(),
            })
        raise self.retry(exc=exc)