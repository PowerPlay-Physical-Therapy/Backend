from collections import defaultdict
from fastapi import HTTPException, APIRouter
from pymongo.errors import PyMongoError
from app.database import get_database
from bson import ObjectId
import os

patientCollection = get_database()["Patients"]
therapistCollection = get_database()["Therapists"]
exerciseCollection = get_database()["Exercises"]
routineCollection = get_database()["Routines"]

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
            category = exercise["category"]
            subcategory = exercise["subcategory"]
            transformed[category][subcategory].append({
                "_id": {"$oid": exercise["_id"]},
                "reps": exercise["reps"],
                "hold": exercise["hold"],
                "sets": exercise["sets"],
                "frequency": exercise["frequency"],
                "description": exercise["description"],
                "thumbnail_url": exercise["thumbnail_url"],
                "video_url": exercise["video_url"],
                "name": exercise["title"]
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
    # print(f"\n\nExercise Found: {exercise}\n\n")

    # Convert the ObjectId to a string
    exercise["_id"] = str(exercise["_id"])
    if exercise is not None:
        return exercise
    else:
        raise HTTPException(status_code=404, detail="Exercise not found")

# fetching routine by id
@router.get("/get_routine/{routine_id}")
def get_routine_by_id(routine_id: str):
    routine = routineCollection.find_one({"_id": ObjectId(routine_id)})
    if routine:
        routine["_id"] = str(routine["_id"])

        exercise_ids = [{"_id":str(exercise["_id"])} for exercise in routine.get("exercises", [])]
        # exercises = exerciseCollection.find({"_id": {"$in": [ObjectId(id) for id in exercise_ids]}})
        # exercises = [str(exercise["_id"]) for exercise in exercises]
        routine["exercises"] = list(exercise_ids)
        # print(f"\n\nRoutine Found: {routine}\n\n")
        return routine
    else:
        raise HTTPException(status_code=404, detail="Routine not found")
    
@router.post("/create_routine")
def create_routine(routine: dict):
    try:
        routine_id = routineCollection.insert_one(routine).inserted_id
        return {"message": "Routine created successfully!", "routine_id": str(routine_id)}
    except PyMongoError as e:
        raise HTTPException(status_code=500, detail="Database update failed")

@router.post("/connect_patient_therapist/{patient_id}/{therapist_id}")
def connect_patient_therapist_bidirectional(patient_id: str, therapist_id: str):
    try:
        # Check if both patient and therapist exist - try both string ID and ObjectId
        patient = patientCollection.find_one({"_id": patient_id})
        if not patient:
            try:
                patient = patientCollection.find_one({"_id": ObjectId(patient_id)})
            except:
                pass
                
        therapist = therapistCollection.find_one({"_id": therapist_id})
        if not therapist:
            try:
                therapist = therapistCollection.find_one({"_id": ObjectId(therapist_id)})
            except:
                pass
        
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        if not therapist:
            raise HTTPException(status_code=404, detail="Therapist not found")
            
        # Add therapist to patient's connections
        patient_update = patientCollection.update_one(
            {"_id": patient["_id"]},  # Use the _id from the found document
            {"$addToSet": {"connections": therapist_id}}
        )
        
        # Add patient to therapist's connections
        therapist_update = therapistCollection.update_one(
            {"_id": therapist["_id"]},  # Use the _id from the found document
            {"$addToSet": {"connections": patient_id}}
        )
        
        if patient_update.modified_count == 1 and therapist_update.modified_count == 1:
            return {"message": "Bidirectional connection established successfully!"}
        elif patient_update.modified_count == 0 and therapist_update.modified_count == 0:
            return {"message": "Bidirectional connection already exists between patient and therapist"}
        else:
            # If one update succeeded and the other didn't, we should rollback
            # Remove the connection from both sides to maintain consistency
            patientCollection.update_one(
                {"_id": patient["_id"]},
                {"$pull": {"connections": therapist_id}}
            )
            therapistCollection.update_one(
                {"_id": therapist["_id"]},
                {"$pull": {"connections": patient_id}}
            )
            raise HTTPException(status_code=500, detail="Failed to establish bidirectional connection properly")
            
    except PyMongoError as e:
        print(f"Database error: {e}")
        # If there's an error, try to clean up any partial updates
        try:
            if 'patient' in locals():
                patientCollection.update_one(
                    {"_id": patient["_id"]},
                    {"$pull": {"connections": therapist_id}}
                )
            if 'therapist' in locals():
                therapistCollection.update_one(
                    {"_id": therapist["_id"]},
                    {"$pull": {"connections": patient_id}}
                )
        except:
            pass  # If cleanup fails, just let the original error propagate
        raise HTTPException(status_code=500, detail=f"Database update failed: {str(e)}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@router.delete("/disconnect_patient_therapist/{patient_id}/{therapist_id}")
def disconnect_patient_therapist_bidirectional(patient_id: str, therapist_id: str):
    try:
        # Check if both patient and therapist exist - try both string ID and ObjectId
        patient = patientCollection.find_one({"_id": patient_id})
        if not patient:
            try:
                patient = patientCollection.find_one({"_id": ObjectId(patient_id)})
            except:
                pass
                
        therapist = therapistCollection.find_one({"_id": therapist_id})
        if not therapist:
            try:
                therapist = therapistCollection.find_one({"_id": ObjectId(therapist_id)})
            except:
                pass
        
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        if not therapist:
            raise HTTPException(status_code=404, detail="Therapist not found")
            
        # Remove therapist from patient's connections
        patient_update = patientCollection.update_one(
            {"_id": patient["_id"]},  # Use the _id from the found document
            {"$pull": {"connections": therapist_id}}
        )
        
        # Remove patient from therapist's connections
        therapist_update = therapistCollection.update_one(
            {"_id": therapist["_id"]},  # Use the _id from the found document
            {"$pull": {"connections": patient_id}}
        )
        
        if patient_update.modified_count == 1 and therapist_update.modified_count == 1:
            return {"message": "Bidirectional connection removed successfully!"}
        elif patient_update.modified_count == 0 and therapist_update.modified_count == 0:
            return {"message": "No bidirectional connection existed between patient and therapist"}
        else:
            # If one update succeeded and the other didn't, we should try to restore consistency
            # Add the connection back to both sides to maintain consistency
            if patient_update.modified_count == 1:
                patientCollection.update_one(
                    {"_id": patient["_id"]},
                    {"$addToSet": {"connections": therapist_id}}
                )
            if therapist_update.modified_count == 1:
                therapistCollection.update_one(
                    {"_id": therapist["_id"]},
                    {"$addToSet": {"connections": patient_id}}
                )
            raise HTTPException(status_code=500, detail="Failed to remove bidirectional connection properly")
            
    except PyMongoError as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail=f"Database update failed: {str(e)}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@router.get("/get_connections/{user_id}/{user_type}")
def get_user_connections(user_id: str, user_type: str):
    try:
        # Determine which collection to use based on user_type
        if user_type.lower() == "patient":
            collection = patientCollection
            connected_collection = therapistCollection
            connected_type = "therapist"
        elif user_type.lower() == "therapist":
            collection = therapistCollection
            connected_collection = patientCollection
            connected_type = "patient"
        else:
            raise HTTPException(status_code=400, detail="Invalid user type. Must be 'patient' or 'therapist'")
        
        # Get the user document - try both string ID and ObjectId
        user = collection.find_one({"_id": user_id})
        if not user:
            # Try with ObjectId if string ID didn't work
            try:
                user = collection.find_one({"_id": ObjectId(user_id)})
            except:
                pass
                
        if not user:
            raise HTTPException(status_code=404, detail=f"{user_type.capitalize()} not found")
        
        # Get the connection IDs
        connection_ids = user.get("connections", [])
        
        # Get the full details of each connected user
        connections = []
        for connected_id in connection_ids:
            # Try both string ID and ObjectId for connected users
            connected_user = connected_collection.find_one({"_id": connected_id})
            if not connected_user:
                try:
                    connected_user = connected_collection.find_one({"_id": ObjectId(connected_id)})
                except:
                    pass
                    
            if connected_user:
                # Convert ObjectId to string for JSON serialization
                connected_user["_id"] = str(connected_user["_id"])
                connections.append(connected_user)
        
        return {
            "user_id": user_id,
            "user_type": user_type,
            "connections": connections,
            "connection_count": len(connections)
        }
        
    except PyMongoError as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
