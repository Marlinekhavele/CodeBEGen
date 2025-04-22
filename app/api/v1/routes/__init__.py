from fastapi import APIRouter

from app.api.v1.routes.code_generation import router as code_generation_router
from app.api.v1.routes.endpoints import router as endpoint_router
from app.api.v1.routes.get_all_endpoints import router as get_all_endpoints_router
from app.api.v1.routes.project_helpers import router as get_project_helpers_router
from app.api.v1.routes.project_models import router as get_project_models_router
from app.api.v1.routes.project_schemas import router as get_project_schemas_router
from app.api.v1.routes.projects import router as project_router
from app.api.v1.routes.streaming import router as streaming_router
from app.api.v1.routes.http_methods_test_endpoint import router as http_methods_test_endpoint_router

router = APIRouter(prefix="/api/v1")
router.include_router(project_router)
router.include_router(endpoint_router)
router.include_router(code_generation_router)
router.include_router(streaming_router)
router.include_router(get_all_endpoints_router)
router.include_router(get_project_models_router)
router.include_router(get_project_schemas_router)
router.include_router(get_project_helpers_router)
router.include_router(http_methods_test_endpoint_router)
