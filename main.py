from fastapi import FastAPI
from routers import users, challenges, submissions, results
from database import create_table

app = FastAPI()
create_table()

app.include_router(users.router)
app.include_router(challenges.router)
app.include_router(submissions.router)
app.include_router(results.router)