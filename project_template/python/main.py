from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware  # New import
from pathlib import Path
from core.router import load_endpoints


app = FastAPI(title="API Starter Template")

# Add CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Load all endpoints
app.include_router(load_endpoints(Path("endpoints")))


@app.get("/")
def root():
    return {
        "message": "FastAPI App Running",
        "endpoints": {
            "health": "/health (GET)",
            "login": "/login (POST)",
            "signup": "/signup (POST)"
        }
    }
