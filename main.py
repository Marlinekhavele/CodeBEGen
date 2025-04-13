import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.routes import router as api_router
from app.api.v1.utils.prompt_manager import PromptManager
from config import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Startup event to load prompt templates
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize prompt templates on startup
    logger.info("Loading prompt templates...")
    try:
        PromptManager.load_templates()
        logger.info("Prompt templates loaded successfully")
    except Exception as e:
        logger.error(f"Error loading prompt templates: {str(e)}")
    yield
    # Clean up resources if needed
    logger.info("Shutting down application...")


app = FastAPI(
    title="CodeBEGen",
    description="AI-powered backend code generation in multiple languages",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configure CORS
origins = ["http://localhost:3000", "http://localhost:7001", "*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware, secret_key=settings.SECRET_KEY, max_age=settings.COOKIE_MAX_AGE
)

# Serve static files if available
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    has_frontend = True
except Exception:
    logger.warning("Static files directory not found. UI will not be available")
    has_frontend = False


# Set up templates
templates = Jinja2Templates(directory="templates")
# Include the main router which has all the sub-routers
app.include_router(api_router)


@app.get("/")
def read_root():
    return {
        "message": "Codebegen API is running",
        "version": "1.0.0",
    }


@app.get("/codebegen", include_in_schema=False)
async def codebegen_ui(request: Request):
    """Serve the CodeBEGen UI from the templates directory"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for all unhandled exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "services": {"api": "online", "generators": "online"}}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.APP_PORT, reload=False)
