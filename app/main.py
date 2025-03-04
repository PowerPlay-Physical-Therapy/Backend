from fastapi.middleware.cors import CORSMiddleware
from typing import Union
from fastapi import FastAPI
from app.routers import patients

app = FastAPI()

app.include_router(patients.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.get("/")
def read_root():
    return "Welcome to the Backend for PowerPlay: Physical Therapy!!"
