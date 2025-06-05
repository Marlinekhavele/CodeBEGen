import os
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from app.api.v1.schemas.code_generation import CodeGenerationRequest
from app.api.v1.services.code_generation import CodeGenerationService

# Sample endpoint code for different HTTP methods
GET_ENDPOINT_CODE = """
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from helpers.product_helpers import get_all_products, get_product_by_id
from database import get_db

router = APIRouter()

@router.get("/products")
def read_products(db: Session = Depends(get_db)):
    return get_all_products(db)

@router.get("/products/{product_id}")
def read_product(product_id: int, db: Session = Depends(get_db)):
    return get_product_by_id(product_id, db)
"""

POST_ENDPOINT_CODE = """
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from helpers.product_helpers import create_product
from database import get_db

router = APIRouter()

@router.post("/products")
def create_product_endpoint(product_data: dict, db: Session = Depends(get_db)):
    return create_product(product_data, db)
"""

# Helper functions for GET endpoints
GET_HELPER_CODE = """
from sqlalchemy.orm import Session
from models.product import Product

def get_all_products(db: Session):
    return db.query(Product).all()

def get_product_by_id(product_id: int, db: Session):
    return db.query(Product).filter(Product.id == product_id).first()
"""

# Helper functions for POST endpoints
POST_HELPER_CODE = """
from sqlalchemy.orm import Session
from models.product import Product

def create_product(product_data: dict, db: Session):
    product = Product(**product_data)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product
"""

# Combined helper code after both endpoints are generated
COMBINED_HELPER_CODE = """
from sqlalchemy.orm import Session
from models.product import Product

def get_all_products(db: Session):
    return db.query(Product).all()

def get_product_by_id(product_id: int, db: Session):
    return db.query(Product).filter(Product.id == product_id).first()

def create_product(product_data: dict, db: Session):
    product = Product(**product_data)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product
"""


class MockLanguageTemplate:
    def __init__(self):
        self.helpers_exist = False
        self.helper_code = None

    def get_component_map(self):
        return {
            "endpoint": "endpoint",
            "model": "model",
            "schema": "schema",
            "helpers": "helpers",
        }

    def get_required_components(self):
        return ["endpoint", "model", "schema", "helpers"]

    def get_file_extension(self):
        return ".py"

    def needs_database(self, code):
        return "db" in code or "Session" in code

    def needs_schema(self, code):
        return "schema" in code or "Schema" in code

    def needs_helpers(self, code):
        # Always return True for this test
        return True

    def _to_snake_case(self, name):
        return "".join(
            ["_" + c.lower() if c.isupper() else c.lower() for c in name]
        ).lstrip("_")

    def get_component_paths(self, project_id, entity_name, **kwargs):
        return {
            "endpoint": f"/app/routes/{self._to_snake_case(entity_name)}.py",
            "model": f"/app/models/{self._to_snake_case(entity_name)}.py",
            "schema": f"/app/schemas/{self._to_snake_case(entity_name)}.py",
            "helpers": f"helpers/{self._to_snake_case(entity_name)}_helpers.py",
        }

    def extract_entity_from_code(self, code):
        return "Product"

    async def generate_component(
        self, component_type, project_id, entity_name, entity_description, **kwargs
    ):
        method = kwargs.get("method", "GET")

        if component_type == "endpoint":
            if method == "GET":
                code = GET_ENDPOINT_CODE
            else:
                code = POST_ENDPOINT_CODE
        elif component_type == "helpers":
            if method == "GET":
                code = GET_HELPER_CODE
            else:
                code = POST_HELPER_CODE
        elif component_type == "model":
            code = """
from sqlalchemy import Column, Integer, String, Float
from database import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    price = Column(Float)
"""
        elif component_type == "schema":
            code = """
from pydantic import BaseModel
from typing import Optional

class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float

class ProductCreate(ProductBase):
    pass

class Product(ProductBase):
    id: int

    class Config:
        orm_mode = True
"""
        else:
            code = f"# Generated {component_type} for {entity_name}"

        return {
            "component_type": component_type,
            "entity_name": entity_name,
            "file_path": self.get_component_paths(project_id, entity_name)[
                component_type
            ],
            "generated_code": code,
            "file_hash": "mock_hash",
            "content_base64": "mock_base64",
        }

    async def generate_migration(self, project_dir, entity_name):
        return {
            "migration_component": {
                "component_type": "migration",
                "entity_name": entity_name,
                "file_path": f"/alembic/versions/create_{entity_name.lower()}.py",
                "generated_code": f"# Migration for {entity_name}",
                "file_hash": "mock_hash",
                "content_base64": "mock_base64",
            }
        }


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.mark.asyncio
class TestCodeGenerationEndToEnd:

    async def test_generate_code_with_multiple_http_methods(self, mock_db):
        """
        Test that generating endpoints with different HTTP methods
        for the same path properly handles helper functions.
        """
        # Create the service
        service = CodeGenerationService()

        # Mock the internal methods
        service._notify_info = AsyncMock()
        service._notify_event = AsyncMock()
        service._commit_files_to_git = AsyncMock(return_value={"success": True})

        # Setup language template
        language_template = MockLanguageTemplate()

        # Setup file system mocks
        helper_file_content = {}
        # Define helper path variable at the beginning of the test
        helper_path = "repos/test-project/helpers/product_helpers.py"

        def mock_file_exists(path):
            # Check if the path exists with either forward or backward slashes
            path_str = str(path)
            normalized_path = path_str.replace("\\", "/")
            for existing_path in helper_file_content:
                existing_path_str = str(existing_path)
                if normalized_path == existing_path_str.replace("\\", "/"):
                    return True
            # Also return True for paths containing "helpers" to allow directory creation
            return "helpers" in path_str

        def mock_file_open(path, *args, **kwargs):
            mode = kwargs.get("mode", args[0] if args else "r")

            # Normalize path for consistent lookups
            path_str = str(path)
            normalized_path = path_str.replace("\\", "/")

            if "r" in mode:
                # For reading, first try with the exact path
                if path in helper_file_content:
                    content = helper_file_content[path]
                else:
                    # Try with normalized path
                    content = ""
                    for existing_path in helper_file_content:
                        existing_path_str = str(existing_path)
                        if normalized_path == existing_path_str.replace("\\", "/"):
                            content = helper_file_content[existing_path]
                            break
                m = mock_open(read_data=content)()
                return m
            else:
                m = mock_open()()

                def write_side_effect(data):
                    if "a" in mode:
                        # Append mode - make sure we look up by normalized path
                        for existing_path in list(helper_file_content.keys()):
                            existing_path_str = str(existing_path)
                            if normalized_path == existing_path_str.replace("\\", "/"):
                                # Append to existing content
                                helper_file_content[existing_path] = (
                                    helper_file_content[existing_path] + data
                                )
                                break
                        else:
                            # If the file doesn't exist yet, create it
                            helper_file_content[path] = data
                    else:
                        # Write mode - replace content
                        helper_file_content[path] = data
                    return len(data)

                m.write.side_effect = write_side_effect
                return m

        os.makedirs("repos/repo.git", exist_ok=True)
        with patch("os.path.exists", side_effect=mock_file_exists), patch(
            "builtins.open", side_effect=mock_file_open
        ), patch(
            "app.api.v1.services.langchain_service.LangchainService.generate_code_with_template",
            new_callable=AsyncMock,
        ) as mock_generate_code_with_template, patch(
            "app.api.v1.services.code_generation.LanguageTemplateFactory.create_template",
            return_value=language_template,
        ), patch(
            "app.api.v1.utils.git_utils.get_repo_url",
            return_value="https://example.com/repo.git",
        ), patch(
            "sqlalchemy.orm.Session", return_value=mock_db
        ), patch(
            "app.api.v1.services.endpoints.EndpointService.create_endpoint",
            return_value={},
        ), patch(
            "app.api.v1.utils.code_merge_utils.extract_py_function_names",
            side_effect=lambda code: (
                ["get_all_products", "get_product_by_id"]
                if "get_all_products" in code
                else ["create_product"]
            ),
        ), patch(
            "app.api.v1.utils.code_merge_utils.extract_required_py_helpers_from_endpoint",
            side_effect=lambda code: (
                ["get_all_products", "get_product_by_id"]
                if "router.get" in code
                else ["create_product"]
            ),
        ):
            # Setup LangchainService mock
            def mock_code_with_template(*args, **kwargs):
                component_type = kwargs.get("component_type", "endpoint")
                entity_name = kwargs.get("entity_name", "Product")
                method = kwargs.get("method", "GET")

                # Use the same logic as MockLanguageTemplate to get code
                if component_type == "endpoint":
                    code = GET_ENDPOINT_CODE if method == "GET" else POST_ENDPOINT_CODE
                elif component_type == "helpers":
                    # For helpers, generate content based on the required method
                    only_functions = kwargs.get("only_functions", [])

                    # Check if helpers file already exists
                    helper_path = "repos/test-project/helpers/product_helpers.py"
                    helpers_exist = helper_path in helper_file_content

                    if helpers_exist:
                        # If helpers file exists, check its content
                        existing_content = helper_file_content.get(helper_path, "")
                        has_get_helpers = "get_all_products" in existing_content

                        # If generating POST helpers and GET helpers exist, use combined code
                        if (
                            method == "POST" or "create_product" in only_functions
                        ) and has_get_helpers:
                            code = COMBINED_HELPER_CODE
                        # If generating GET helpers (regardless of POST exists or not)
                        elif (
                            method == "GET"
                            or "get_all_products" in only_functions
                            or "get_product_by_id" in only_functions
                        ):
                            # Include both GET and POST helpers when both are needed
                            if (
                                "create_product" in existing_content
                                or "create_product" in only_functions
                            ):
                                code = COMBINED_HELPER_CODE
                            else:
                                code = GET_HELPER_CODE
                        else:
                            # Only POST helpers
                            code = POST_HELPER_CODE
                    else:
                        # No existing helper file
                        if (
                            method == "GET"
                            or "get_all_products" in only_functions
                            or "get_product_by_id" in only_functions
                        ):
                            if method == "POST" or "create_product" in only_functions:
                                code = COMBINED_HELPER_CODE
                            else:
                                code = GET_HELPER_CODE
                        elif method == "POST" or "create_product" in only_functions:
                            code = POST_HELPER_CODE
                        else:
                            code = "# No helper functions required"
                elif component_type == "model":
                    code = """
from sqlalchemy import Column, Integer, String, Float
from database import Base

class Product(Base):
    __tablename__ = \"products\"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    price = Column(Float)
"""
                elif component_type == "schema":
                    code = """
from pydantic import BaseModel
from typing import Optional

class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
class ProductCreate(ProductBase):
    pass
class Product(ProductBase):
    id: int
    class Config:
        orm_mode = True
"""
                else:
                    code = f"# Generated {component_type} for {entity_name}"
                return {
                    "file_path": language_template.get_component_paths(
                        "test-project", entity_name
                    )[component_type],
                    "generated_code": code,
                    "content_base64": "mock_base64",
                    "file_hash": "mock_hash",
                    "language": "python",
                }

            mock_generate_code_with_template.side_effect = mock_code_with_template
            # STEP 1: Generate the GET endpoint
            get_request = CodeGenerationRequest(
                project_id="test-project",
                prompt="Create a product API with GET method",
                language="python",
                method="GET",
                endpoint_path="/products",
            )

            get_response = await service.generate_code(get_request, mock_db)

            # Verify GET generation was successful
            assert get_response.success
            assert get_response.result is not None

            # Check that helper file exists after GET request
            assert (
                helper_path in helper_file_content
            ), f"Helper path {helper_path} not found in helper_file_content keys after GET: {list(helper_file_content.keys())}"

            # Get the helper content
            helper_content = helper_file_content[helper_path]
            print(f"Helper content after GET: {helper_content}")

            # Check for GET helper functions            assert "get_all_products" in helper_content, "get_all_products not found in helper content after GET"
            assert (
                "get_product_by_id" in helper_content
            ), "get_product_by_id not found in helper content after GET"
            # STEP 2: Generate the POST endpoint for the same path
            post_request = CodeGenerationRequest(
                project_id="test-project",
                prompt="Create a product API with POST method",
                language="python",
                method="POST",
                endpoint_path="/products",
            )
            # Mocked to show helpers exist now
            language_template.helpers_exist = True

            post_response = await service.generate_code(post_request, mock_db)

            # Verify POST generation was successful
            assert post_response.success
            assert post_response.result is not None

            # Check that helper file still exists after POST request
            assert (
                helper_path in helper_file_content
            ), f"Helper path {helper_path} not found after POST request"

            # Get the updated helper content
            helper_content = helper_file_content[helper_path]
            print(f"Updated helper content after POST: {helper_content}")

            # Check for all helper functions in the combined code
            assert (
                "get_all_products" in helper_content
            ), "get_all_products not found in helper content after POST"
            assert (
                "get_product_by_id" in helper_content
            ), "get_product_by_id not found in helper content after POST"
            assert (
                "create_product" in helper_content
            ), "create_product not found in helper content after POST"

            # Debug any issues with the helper content
            if "get_all_products" not in helper_content:
                print(
                    f"All keys in helper_file_content: {list(helper_file_content.keys())}"
                )
                for key, value in helper_file_content.items():
                    print(f"Content for {key}: {value[:100]}...")
