import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


from app.api import router as api_router
from config import settings


app = FastAPI(
    title="codebegen API",
    description="codebegen API for managing projects and endpoints",
    version="1.0.0",
    docs_url="/docs"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
def read_root():
    return {
        "message": "codebegen API is running",
        "version": "1.0.0",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=settings.APP_PORT, 
        reload=False
    )