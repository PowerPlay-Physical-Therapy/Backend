from typing import Union
from fastapi import FastAPI
from app.routers import patients

app = FastAPI()

app.include_router(patients.router)


@app.get("/")
def read_root():
    return "Welcome to the Backend for PowerPlay: Physical Therapy!!"
