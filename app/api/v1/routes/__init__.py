from fastapi import APIRouter

from app.api.v1.routes.endpoints import router as endpoint_router

router = APIRouter(prefix="/v1")
router.include_router(endpoint_router)
