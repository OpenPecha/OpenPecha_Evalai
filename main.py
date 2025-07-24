from fastapi import FastAPI
from routers import user, challenge, submission, result, category, model
from database import create_table
from db_models import *


app = FastAPI()
create_table()


# Allow requests from frontend dev server (adjust the port if needed)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:5173"],  # Default Vite port
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

app.include_router(user.router)
app.include_router(category.router)
app.include_router(challenge.router)
app.include_router(submission.router)
app.include_router(result.router)
# app.include_router(model.router)