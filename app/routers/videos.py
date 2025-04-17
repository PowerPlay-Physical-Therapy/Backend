from collections import defaultdict
from fastapi import HTTPException, APIRouter, UploadFile, status
from pymongo.errors import PyMongoError
from app.database import get_database
from uuid import uuid4
import os
import magic
import boto3

SUPPORTED_FILE_TYPES = {
    "video/mp4" : "mp4",
    "video/mov" : "mov",
    "application/pdf" : "pdf",
}

AWS_BUCKET = "powerplaypatientvids"
s3 = boto3.resource('s3',
    aws_access_key_id=os.getenv("PATIENTVIDS_KEY_ID"),
    aws_secret_access_key=os.getenv("PATIENTVIDS_SECRET_KEY"),
    region_name=os.getenv("us-east-2")
)

bucket = s3.Bucket(AWS_BUCKET)

async def s3_upload(contents, name):
    bucket.put_object(Key=name, Body=contents)

# custom videos
CUSTOM_VIDS_BUCKET = "custom-exercise-vids"
bucket_2 = s3.Bucket(CUSTOM_VIDS_BUCKET)

s3 = boto3.resource('s3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_KEY_ID"),
    region_name=os.getenv("AWS_REGION")
)

async def s3_custom_vids_upload(contents, name):
    bucket_2.put_object(Key=name, Body=contents)


patientCollection = get_database()["Patients"]
therapistCollection = get_database()["Therapists"]
exerciseCollection = get_database()["Exercises"]
routineCollection = get_database()["Routines"]

router = APIRouter( tags=["Videos"])


@router.post("/upload_video")
async def upload(file: UploadFile | None = None):
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")
    
    contents = await file.read()
    file_size = len(contents)
    if file_size > 20 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(status_code=400, detail="File size exceeds limit of 20 MB")
    file_type = magic.from_buffer(buffer=contents, mime=True)
    await s3_upload(contents=contents, name=f"{uuid4()}.{SUPPORTED_FILE_TYPES[file_type]}")
        
    