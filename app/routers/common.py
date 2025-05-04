from collections import defaultdict
from fastapi import HTTPException, APIRouter, UploadFile, status, Request
from pymongo.errors import PyMongoError
from app.database import get_database
from bson import ObjectId
from uuid import uuid4
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pymongo.errors import PyMongoError
import os
from datetime import datetime, timezone


patientCollection = get_database()["Patients"]
therapistCollection = get_database()["Therapists"]
exerciseCollection = get_database()["Exercises"]
routineCollection = get_database()["Routines"]
messageCollection = get_database()["Messages"]
connectionCollection = get_database()["Connections"]

router = APIRouter(tags=["Common"])

@router.get("/get_explore_collection")
def get_explore_collection():
    exercises = exerciseCollection.find()
    exercise_list = []
    for exercise in exercises:
        exercise["_id"] = str(exercise["_id"])
        exercise_list.append(exercise)

    def modify_exercises(exercise_list):
        transformed = defaultdict(lambda: defaultdict(list))
        for exercise in exercise_list:
            category = exercise.get("category")
            subcategory = exercise.get("subcategory")
            transformed[category][subcategory].append({
                "_id": {"$oid": exercise.get("_id")},
                "reps": exercise.get("reps"),
                "hold": exercise.get("hold"),
                "sets": exercise.get("sets"),
                "frequency": exercise.get("frequency"),
                "description": exercise.get("description"),
                "thumbnail_url": exercise.get("thumbnail_url"),
                "video_url": exercise.get("video_url"),
                "name": exercise.get("title"),
            })
        result = []
        for category, subcategories in transformed.items():
            result.append({
                "title": category,
                "subcategory": [
                    {"subtitle": subcat, "exercises": exercises}
                    for subcat, exercises in subcategories.items()
                ]
            })
        return result

    return modify_exercises(exercise_list)

@router.get("/get_exercise/{exercise_id}")
def get_exercise_by_id(exercise_id: str):
    exercise = exerciseCollection.find_one({"_id": ObjectId(exercise_id)})
    if exercise is not None:
        exercise["_id"] = str(exercise["_id"])
        return exercise
    else:
        raise HTTPException(status_code=404, detail="Exercise not found")
    

@router.get("/get_routine/{routine_id}")
def get_routine_by_id(routine_id: str):
    routine = routineCollection.find_one({"_id": ObjectId(routine_id)})

    if routine:
        routine["_id"] = str(routine["_id"])
        # Extract exercise ObjectIds
        exercise_ids = [exercise["_id"]
                        for exercise in routine.get("exercises", [])]

        # Fetch full exercise documents
        exercises = list(exerciseCollection.find(
            {"_id": {"$in": exercise_ids}}))

        # Convert ObjectId to string for each exercise
        for exercise in exercises:
            exercise["_id"] = str(exercise["_id"])

        # Attach full exercises to routine
        routine["exercises"] = exercises

        return routine
    else:
        raise HTTPException(status_code=404, detail="Routine not found")

@router.post("/create_routine")
def create_routine(routine: dict):
    try:
        # Validate exercises array (if any) and ensure they are all ObjectId references
        if "exercises" in routine:
            for exercise in routine["exercises"]:
                if "_id" in exercise and not isinstance(exercise["_id"], ObjectId):
                    exercise["_id"] = ObjectId(exercise["_id"])  # Convert string IDs to ObjectId

        # Insert new routine with exercises
        routine_id = routineCollection.insert_one(routine).inserted_id

        # Return response with the routine ID
        return {"message": "Routine created successfully!", "routine_id": str(routine_id)}

    except PyMongoError as e:
        print(f"Database Insertion Error: {e}")
        raise HTTPException(status_code=500, detail="Database insertion failed")
    except Exception as e:
        print(f"Unexpected Error: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


def convert_message(doc):
    doc["_id"] = str(doc["_id"])
    doc["timestamp"] = doc["timestamp"]
    return doc


@router.get("/messages/{user1}/{user2}")
def get_messages(user1: str, user2: str):
    # Query for all messages between user1 and user2
    cursor = messageCollection.find({
        "$or": [
            {"sender_id": user1, "receiver_id": user2},
            {"sender_id": user2, "receiver_id": user1}
        ]
    }).sort("timestamp", 1)

    messages = []
    for msg in cursor:
        messages.append(convert_message(msg))

    return JSONResponse(content=jsonable_encoder(messages))

@router.put("/message/{user1}/{user2}")
async def update_messages(user1: str, user2: str, request: Request):
    data = await request.json()
    message = data.get("message")
    type = data.get("type")
    tempObj: dict = {
        "sender_id": user1,
        "receiver_id": user2,
        "type": type,
        "read": False,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "message": message}
    
    try: 
        message_id = messageCollection.insert_one(tempObj)
        return {"message": "Message sent successfully", "message_id" : str(message_id.inserted_id)}
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database update failed")

# @router.websocket("/chat")
# def chat(websocket):

@router.post("/connect_patient_therapist/{patient_id}/{therapist_id}")
def connect_patient_therapist_bidirectional(patient_id: str, therapist_id: str, request: Request):
    try:
        print("Connecting patient:", patient_id, "to therapist:", therapist_id)

        role = request.headers.get("X-User-Role", "patient")  # Defaults to patient
        status = "accepted" if role == "therapist" else "pending"
        print("Using role:", role, "=> status:", status)

        existing = connectionCollection.find_one({
            "patient_id": patient_id,
            "therapist_id": therapist_id
        })

        if role == "therapist":
            patient = patientCollection.find_one({"_id": patient_id})
            therapist = therapistCollection.find_one({"_id": therapist_id})

            if not patient:
                raise HTTPException(status_code=404, detail="Patient not found")
            if not therapist:
                raise HTTPException(status_code=404, detail="Therapist not found")

            if therapist_id in patient.get("connections", []):
                raise HTTPException(status_code=400, detail="Connection already exists")
            if patient_id in therapist.get("connections", []):
                raise HTTPException(status_code=400, detail="Connection already exists")
            updated_item_1 = patientCollection.update_one(
                {"_id": patient_id},
                {"$addToSet": {"connections": therapist_id}}
            )
            updated_item_2 = therapistCollection.update_one(
                {"_id": therapist_id},
                {"$addToSet": {"connections": patient_id}}
            )

            if updated_item_1.modified_count != 1 or updated_item_2.modified_count != 1:
                raise HTTPException(status_code=400, detail="Failed to add connection")
        
        if existing:
            return {"message": "Connection already exists"}

        connection = {
            "patient_id": patient_id,
            "therapist_id": therapist_id,
            "status": status
        }

        connectionCollection.insert_one(connection)
        return {"message": "Connection request created", "status": status}

    except Exception as e:
        print("Error creating connection:", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/accept_connection/{patient_id}/{therapist_id}")
def accept_connection(patient_id: str, therapist_id: str):
    try:
        result = connectionCollection.update_one(
            {"patient_id": patient_id, "therapist_id": therapist_id, "status": "pending"},
            {"$set": {"status": "accepted"}}
        )

        patient = patientCollection.find_one({"_id": patient_id})
        therapist = therapistCollection.find_one({"_id": therapist_id})

        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        if not therapist:
            raise HTTPException(status_code=404, detail="Therapist not found")

        if therapist_id in patient.get("connections", []):
            raise HTTPException(status_code=400, detail="Connection already exists")
        if patient_id in therapist.get("connections", []):
            raise HTTPException(status_code=400, detail="Connection already exists")
        updated_item_1 = patientCollection.update_one(
                {"_id": patient_id},
                {"$addToSet": {"connections": therapist_id}}
            )
        updated_item_2 = therapistCollection.update_one(
                {"_id": therapist_id},
                {"$addToSet": {"connections": patient_id}}
            )

        if updated_item_1.modified_count != 1 or updated_item_2.modified_count != 1:
            raise HTTPException(status_code=400, detail="Failed to add connection")

        if result.modified_count == 1:
            return {"message": "Connection accepted"}
        else:
            raise HTTPException(status_code=404, detail="Pending connection not found")

    except Exception as e:
        print("Error accepting connection:", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/get_connections/{user_id}/{user_type}")
def get_user_connections(user_id: str, user_type: str):
    try:
        if user_type.lower() == "patient":
            connections = connectionCollection.find({"patient_id": user_id})
            other_collection = therapistCollection
            id_key = "therapist_id"
        elif user_type.lower() == "therapist":
            connections = connectionCollection.find({"therapist_id": user_id})
            other_collection = patientCollection
            id_key = "patient_id"
        else:
            raise HTTPException(status_code=400, detail="Invalid user type")

        results = []
        for conn in connections:
            try:
                user = other_collection.find_one({"_id": conn[id_key]})
                if user:
                    user_info = {
                        "_id": str(user["_id"]),
                        "firstname": user.get("firstname", ""),
                        "lastname": user.get("lastname", ""),
                        "imageUrl": user.get("imageUrl"),
                        "status": conn.get("status", "accepted"),
                        "expoPushToken": user.get("expoPushToken", ""),
                    }
                    results.append(user_info)
            except Exception as inner_e:
                print(f"Skipping bad connection entry: {conn} | Error: {inner_e}")
                continue

        return {
            "user_id": user_id,
            "user_type": user_type,
            "connections": results,
            "connection_count": len(results)
        }

    except Exception as e:
        print("Error fetching connections:", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/disconnect_patient_therapist/{patient_id}/{therapist_id}")
def disconnect_patient_therapist(patient_id: str, therapist_id: str):
    try:
        patient = patientCollection.find_one({"_id" : patient_id})
        therapist = therapistCollection.find_one({"_id" : therapist_id})
        if patient and therapist:
            if therapist_id not in patient.get("connections", []):
                raise HTTPException(status_code=400, detail="Connection does not exist")
            if patient_id not in therapist.get("connections", []):
                raise HTTPException(status_code=400, detail="Connection does not exist")
            updated_item_1 = patientCollection.update_one(
                {"_id": patient_id},
                {"$pull": {"connections": therapist_id}}
            )
            updated_item_2 = therapistCollection.update_one(
                {"_id": therapist_id},
                {"$pull": {"connections": patient_id}}
            )
            if updated_item_1.modified_count != 1 or updated_item_2.modified_count != 1:
                raise HTTPException(status_code=400, detail="Failed to remove connection")
        else:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        result = connectionCollection.delete_one({
            "patient_id": patient_id,
            "therapist_id": therapist_id
        })

        if result.deleted_count == 1:
            return {"message": "Connection removed successfully"}
        else:
            raise HTTPException(status_code=404, detail="Connection not found")
    except Exception as e:
        print("Error removing connection:", str(e))
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/reject_connection/{patient_id}/{therapist_id}")
def reject_connection(patient_id: str, therapist_id: str):
    try:
        result = connectionCollection.delete_one({
            "patient_id": patient_id,
            "therapist_id": therapist_id,
            "status": "pending"
        })

        if result.deleted_count == 1:
            return {"message": "Connection rejected and removed"}
        else:
            raise HTTPException(status_code=404, detail="Pending connection not found")
    except Exception as e:
        print("Error rejecting connection:", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete_custom_routine/{therapist_id}/{routine_id}")
def delete_custome_routine(therapist_id: str, routine_id: str):
    try:
        therapist = therapistCollection.find_one({"_id": therapist_id})
        routine = routineCollection.find_one({"_id": ObjectId(routine_id)})
        patients = patientCollection.find({
            "assigned_routines": {
                "$elemMatch": {"_id": ObjectId(routine_id)}
            }
        })

        if patients:
            for patient in patients:
                patientCollection.update_one(
                    {"_id": patient["_id"]},
                    {"$pull": {"assigned_routines": {"_id": ObjectId(routine_id)}}}
                )
        
        if therapist and routine:
            updated_therapist = therapistCollection.update_one(
                {"_id": therapist_id},
                {"$pull": {"custom_routines": {"_id": ObjectId(routine_id)}}}
            )

            # Delete the routine from the Routines collection
            for exercise in routine.get("exercises", []):
                exercise_id = exercise.get("_id")
                if exercise_id:
                    exerciseCollection.delete_one({"_id": ObjectId(exercise_id)})
            
            updated_routine = routineCollection.delete_one({"_id": ObjectId(routine_id)})


            if updated_therapist.modified_count == 1 and updated_routine.deleted_count == 1:
                return {"message": "Custom Routine deleted successfully!"}
            else:
                raise HTTPException(
                    status_code=400, detail="Failed to delete routine")
        else:
            # Item not found
            raise HTTPException(status_code=404, detail="Therapist/patient not found")
        

    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database update failed")

@router.delete("/delete_chat/{user1}/{user2}")
def delete_chat(user1: str, user2: str):
    try:
        result = messageCollection.delete_many({
            "$or": [
                {"sender_id": user1, "receiver_id": user2},
                {"sender_id": user2, "receiver_id": user1}
            ]
        })

        if result.deleted_count > 0:
            return {"message": "Chat deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="No chat found")
    except Exception as e:
        print("Error deleting chat:", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/toggle_mute/{patient_id}/{therapist_id}")
async def toggle_mute(patient_id: str, therapist_id: str):
    try:
        # Find the connection
        connection = connectionCollection.find_one({
            "patient_id": patient_id,
            "therapist_id": therapist_id
        })

        if not connection:
            raise HTTPException(status_code=404, detail="Connection not found")

        # Get current mute status or default to False
        current_mute_status = connection.get("is_muted", False)
        
        # Toggle the mute status
        result = connectionCollection.update_one(
            {
                "patient_id": patient_id,
                "therapist_id": therapist_id
            },
            {"$set": {"is_muted": not current_mute_status}}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to update mute status")

        return {
            "message": f"Successfully {'muted' if not current_mute_status else 'unmuted'} the connection",
            "patient_id": patient_id,
            "therapist_id": therapist_id,
            "is_muted": not current_mute_status
        }

    except PyMongoError as e:
        print(f"Database Error: {e}")
        raise HTTPException(status_code=500, detail="Database operation failed")
    except Exception as e:
        print(f"Unexpected Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))