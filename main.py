from fastapi import FastAPI
from routers import user, challenge, submission, result, category, model
from database import create_table
from db_models import *
import uvicorn
from dotenv import load_dotenv
import os
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI(
    title="OpenPecha Evalai API",
    description="API for OpenPecha Evalai",
    version="0.0.1"
)
create_table()

# CORS configuration
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS", 
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
)
origins = [origin.strip() for origin in allowed_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user.router)
app.include_router(category.router)
app.include_router(model.router)
app.include_router(challenge.router)
app.include_router(submission.router)
app.include_router(result.router)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )