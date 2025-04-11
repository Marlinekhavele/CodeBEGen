from fastapi import APIRouter

from app.api.v1.routes.endpoints import router as endpoint_router
from app.api.v1.routes.projects import router as project_router

router = APIRouter(prefix="/api/v1")
router.include_router(project_router)
router.include_router(endpoint_router)
