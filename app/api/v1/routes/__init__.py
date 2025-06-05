from fastapi import APIRouter

from app.api.v1.endpoints.quality_dashboard import router as quality_dashboard_router
from app.api.v1.endpoints.quality_pipeline import router as quality_pipeline_router
from app.api.v1.routes.auto_fix import router as auto_fix_router
from app.api.v1.routes.code_generation import router as code_generation_router
from app.api.v1.routes.endpoints import router as endpoint_router
from app.api.v1.routes.get_all_endpoints import router as get_all_endpoints_router
from app.api.v1.routes.http_methods_test_endpoint import (
    router as http_methods_test_endpoint_router,
)
from app.api.v1.routes.project_db import router as get_project_db_router
from app.api.v1.routes.project_db_migration import router as project_db_migration_router
from app.api.v1.routes.project_docs import router as get_project_docs_router
from app.api.v1.routes.project_helpers import router as get_project_helpers_router
from app.api.v1.routes.project_migrations import router as project_migrations_router
from app.api.v1.routes.project_models import router as get_project_models_router
from app.api.v1.routes.project_schemas import router as get_project_schemas_router
from app.api.v1.routes.project_structure import router as project_structure_router
from app.api.v1.routes.projects import router as project_router
from app.api.v1.routes.streaming import router as streaming_router

router = APIRouter(prefix="/api/v1")
router.include_router(project_router)
router.include_router(endpoint_router)
router.include_router(code_generation_router)
router.include_router(auto_fix_router)
router.include_router(streaming_router)
router.include_router(get_all_endpoints_router)
router.include_router(get_project_models_router)
router.include_router(get_project_schemas_router)
router.include_router(get_project_helpers_router)
router.include_router(get_project_docs_router)
router.include_router(project_migrations_router)
router.include_router(http_methods_test_endpoint_router)
router.include_router(get_project_db_router)
router.include_router(project_db_migration_router)
router.include_router(project_structure_router)
router.include_router(quality_pipeline_router)
router.include_router(quality_dashboard_router)
