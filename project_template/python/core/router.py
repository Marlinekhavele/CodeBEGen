import importlib.util
from pathlib import Path
from fastapi import APIRouter

def load_endpoints(base_path: Path = Path("endpoints")) -> APIRouter:
    router = APIRouter()
    
    for file_path in base_path.glob("**/*.*.py"):
        # Load the module
        spec = importlib.util.spec_from_file_location("", file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Find the router in the module and include it directly
        if hasattr(module, "router"):
            router.include_router(module.router)

    return router
