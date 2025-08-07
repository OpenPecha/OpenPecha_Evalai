from fastapi import FastAPI
from fastapi.security import HTTPBearer
from fastapi.openapi.utils import get_openapi
from routers import user, challenge, submission, result, category, model
from database import create_table
import uvicorn
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()



# Auth0 configuration
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")




# HTTP Bearer scheme for API endpoints
security = HTTPBearer()

app = FastAPI(
    title="OpenPecha EvalAI API",
    description="API for OpenPecha evaluation challenges with Auth0 JWT authentication",
    version="1.0.0",
    docs_url="/docs",  # Enable default docs
    redoc_url="/redoc",  # Enable default redoc
    openapi_url="/openapi.json"
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        openapi_version="3.0.3"
    )
    
    # Ensure openapi version is set
    openapi_schema["openapi"] = "3.0.3"
    
    # Initialize components if not present
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    if "securitySchemes" not in openapi_schema["components"]:
        openapi_schema["components"]["securitySchemes"] = {}
    
    # Clear any existing security schemes and set only Auth0Bearer
    openapi_schema["components"]["securitySchemes"] = {
        "Auth0Bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Auth0 JWT Token - Use your Auth0 access token"
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

create_table()


# Allow requests from frontend dev server (adjust the port if needed)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:5173"],  # Default Vite port
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )







@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Welcome to OpenPecha EvalAI API", "status": "success"}








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