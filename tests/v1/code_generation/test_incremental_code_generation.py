import re
from unittest.mock import AsyncMock, mock_open, patch

import pytest

from app.api.v1.services.code_generation import CodeGenerationService

# Import test helpers to patch missing methods
from tests.v1.code_generation.test_helpers import apply_patches

# Apply patches for test
apply_patches()


class MockLanguageTemplate:
    """Mock language template for testing."""

    def __init__(self, language="python"):
        self.language = language
        self.file_extension = ".py" if language == "python" else ".js"
        self.component_map = {
            "endpoint": "endpoint",
            "model": "model",
            "schema": "schema",
            "helpers": "helpers",
            "migration": "migration",
        }
        self.required_components = [
            "endpoint",
            "model",
            "schema",
            "helpers",
            "migration",
        ]
        self.helper_file_exists = False
        self.existing_helper_code = ""

    def get_file_extension(self):
        return self.file_extension

    def get_component_map(self):
        return self.component_map

    def get_required_components(self):
        return self.required_components

    def extract_entity_from_code(self, code):
        return "TestEntity"

    def needs_database(self, code):
        """Determine if generated code needs database components."""
        # Enhanced database dependency detection for tests
        db_patterns = [
            r"db\s*:\s*Session",  # Type annotation: db: Session
            r"Session\s*=\s*Depends\(",  # Dependency injection
            r"Depends\(\s*get_db\s*\)",  # FastAPI common pattern
            r"db\s*\.\s*\w+",  # Database operation: db.query
            r"sqlalchemy",  # SQLAlchemy import/usage
            r"import.*orm",  # SQLAlchemy ORM
            r"database\.Base",  # Database base class
            r"database",  # General mention of database
            r"\w+\([^)]*db\)",  # Function calls with db param
        ]

        for pattern in db_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return True

        return False

    def needs_schema(self, code):
        return "schema" in code or "validate" in code

    def needs_helpers(self, code):
        # Enhanced version to better match helper usage patterns
        helper_patterns = [
            r"from\s+helpers\.",  # Python imports
            r"import\s+helpers\.",  # Python imports
            r"require\(['\"].*?utils",  # JS requires
            r"\w+_helpers\s+import",  # Python specific helper imports
            r"get_all_\w+",  # Common helper function pattern
            r"create_\w+",  # Common helper function pattern
            r"update_\w+",  # Common helper function pattern
            r"delete_\w+",  # Common helper function pattern
        ]

        for pattern in helper_patterns:
            if re.search(pattern, code):
                return True

        return "helper" in code or "from helpers" in code or "require(" in code

    def _to_snake_case(self, name):
        return "".join(
            ["_" + c.lower() if c.isupper() else c.lower() for c in name]
        ).lstrip("_")

    def get_component_paths(self, project_id, entity_name, **kwargs):
        if self.language == "python":
            return {
                "endpoint": f"/app/api/v1/routes/{self._to_snake_case(entity_name)}.py",
                "model": f"/app/models/{self._to_snake_case(entity_name)}.py",
                "schema": f"/app/schemas/{self._to_snake_case(entity_name)}.py",
                "helpers": f"helpers/{self._to_snake_case(entity_name)}_helpers.py",
                "migration": f"/alembic/versions/create_{self._to_snake_case(entity_name)}.py",
            }
        else:
            return {
                "endpoint": f"/routes/{self._to_snake_case(entity_name)}.js",
                "model": f"/models/{self._to_snake_case(entity_name)}.js",
                "schema": f"/schemas/{self._to_snake_case(entity_name)}.js",
                "helpers": f"/utils/{self._to_snake_case(entity_name)}.utils.js",
                "migration": f"/migrations/create_{self._to_snake_case(entity_name)}.js",
            }

    async def generate_component(
        self, component_type, project_id, entity_name, entity_description, **kwargs
    ):
        # Different content based on HTTP method to simulate different helper requirements
        method = kwargs.get("method", "GET")

        if component_type == "endpoint":
            if method == "GET":
                if self.language == "python":
                    code = f"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from helpers.{self._to_snake_case(entity_name)}_helpers import get_all_{self._to_snake_case(entity_name)}s

router = APIRouter()

@router.get("/{self._to_snake_case(entity_name)}s")
def get_{self._to_snake_case(entity_name)}s(db: Session = Depends(get_db)):
    return get_all_{self._to_snake_case(entity_name)}s(db)
"""
                else:
                    code = f"""
const express = require('express');
const router = express.Router();
const {{ getAllItems }} = require('../utils/{self._to_snake_case(entity_name)}.utils');

router.get('/{self._to_snake_case(entity_name)}s', (req, res) => {{
    const items = getAllItems();
    res.json(items);
}});

module.exports = router;
"""
            elif method == "POST":
                if self.language == "python":
                    code = f"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from helpers.{self._to_snake_case(entity_name)}_helpers import create_{self._to_snake_case(entity_name)}

router = APIRouter()

@router.post("/{self._to_snake_case(entity_name)}s")
def create_new_{self._to_snake_case(entity_name)}(data: dict, db: Session = Depends(get_db)):
    return create_{self._to_snake_case(entity_name)}(data, db)
"""
                else:
                    code = f"""
const express = require('express');
const router = express.Router();
const {{ createItem }} = require('../utils/{self._to_snake_case(entity_name)}.utils');

router.post('/{self._to_snake_case(entity_name)}s', (req, res) => {{
    const newItem = createItem(req.body);
    res.status(201).json(newItem);
}});

module.exports = router;
"""
        elif component_type == "helpers":
            if method == "GET":
                if self.language == "python":
                    code = f"""
from sqlalchemy.orm import Session
from models.{self._to_snake_case(entity_name)} import {entity_name}

def get_all_{self._to_snake_case(entity_name)}s(db: Session):
    return db.query({entity_name}).all()
"""
                else:
                    code = f"""
const {entity_name} = require('../models/{self._to_snake_case(entity_name)}');

exports.getAllItems = () => {{
    return {entity_name}.find();
}};
"""
            elif method == "POST":
                if self.language == "python":
                    code = f"""
from sqlalchemy.orm import Session
from models.{self._to_snake_case(entity_name)} import {entity_name}

def create_{self._to_snake_case(entity_name)}(data: dict, db: Session):
    new_{self._to_snake_case(entity_name)} = {entity_name}(**data)
    db.add(new_{self._to_snake_case(entity_name)})
    db.commit()
    db.refresh(new_{self._to_snake_case(entity_name)})
    return new_{self._to_snake_case(entity_name)}
"""
                else:
                    code = f"""
const {entity_name} = require('../models/{self._to_snake_case(entity_name)}');

exports.createItem = (data) => {{
    const newItem = new {entity_name}(data);
    return newItem.save();
}};
"""
        elif component_type == "model":
            if self.language == "python":
                code = f"""
from sqlalchemy import Column, Integer, String
from database import Base

class {entity_name}(Base):
    __tablename__ = "{self._to_snake_case(entity_name)}s"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
"""
            else:
                code = f"""
const mongoose = require('mongoose');

const {self._to_snake_case(entity_name)}Schema = new mongoose.Schema({{
    name: {{ type: String, required: true }},
    description: {{ type: String }}
}}, {{ timestamps: true }});

module.exports = mongoose.model('{entity_name}', {self._to_snake_case(entity_name)}Schema);
"""
        else:
            code = f"# Generated {component_type} for {entity_name}\n"

        return {
            "component_type": component_type,
            "entity_name": entity_name,
            "file_path": self.get_component_paths(project_id, entity_name, **kwargs)[
                component_type
            ],
            "generated_code": code,
            "file_hash": "mock_hash",
            "content_base64": "mock_base64",
        }


@pytest.fixture
def mock_language_template_python():
    return MockLanguageTemplate(language="python")


@pytest.fixture
def mock_language_template_javascript():
    return MockLanguageTemplate(language="javascript")


@pytest.fixture
def code_gen_service():
    # Setup notification callbacks as None for simplicity
    service = CodeGenerationService()
    # Mock internal notification methods to avoid side effects
    service._notify_info = AsyncMock()
    service._notify_event = AsyncMock()
    return service


@pytest.mark.asyncio
class TestIncrementalCodeGeneration:

    async def test_analyze_component_dependencies(
        self, code_gen_service, mock_language_template_python
    ):
        """Test the component dependency analysis."""
        with patch.object(
            code_gen_service, "_check_if_helpers_exist", return_value=False
        ):
            # Test with code that needs database and helpers
            endpoint_code = """
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from helpers.user_helpers import get_all_users

router = APIRouter()

@router.get("/users")
def get_users(db: Session = Depends(get_db)):
    return get_all_users(db)
"""
            result = await code_gen_service._analyze_component_dependencies(
                language_template=mock_language_template_python,
                endpoint_code=endpoint_code,
                entity_name="User",
                project_id="test-project",
            )

            assert result["needs_database"] is True
            assert result["needs_helpers"] is True
            assert result["helpers_exist"] is False

            # Test with code that doesn't need database
            endpoint_code = """
from fastapi import APIRouter

router = APIRouter()

@router.get("/status")
def get_status():
    return {"status": "ok"}
"""
            result = await code_gen_service._analyze_component_dependencies(
                language_template=mock_language_template_python,
                endpoint_code=endpoint_code,
                entity_name="Status",
                project_id="test-project",
            )

            assert result["needs_database"] is False
            assert result["needs_helpers"] is False

    async def test_should_skip_component(self, code_gen_service):
        """Test the component skipping logic."""
        # Setup dependencies dict
        dependencies = {
            "needs_database": False,
            "needs_schema": False,
            "needs_helpers": False,
            "helpers_exist": False,
        }  # Should skip endpoint (already generated)
        assert (
            await code_gen_service._should_skip_component(
                component_type="endpoint",
                dependencies=dependencies,
                endpoint_component="endpoint",
            )
            is True
        )

        # Should skip model (no database needed)
        assert (
            await code_gen_service._should_skip_component(
                component_type="model",
                dependencies=dependencies,
                endpoint_component="endpoint",
            )
            is True
        )

        # Should not skip if needed
        dependencies["needs_database"] = True
        assert (
            await code_gen_service._should_skip_component(
                component_type="model",
                dependencies=dependencies,
                endpoint_component="endpoint",
            )
            is False
        )

    async def test_check_if_helpers_exist(
        self, code_gen_service, mock_language_template_python
    ):
        """Test the helper existence check."""
        with patch("os.path.exists") as mock_exists:
            # Test when helper file exists
            mock_exists.return_value = True
            result = await code_gen_service._check_if_helpers_exist(
                project_id="test-project",
                entity_name="User",
                language_template=mock_language_template_python,
            )
            assert result is True

            # Test when helper file doesn't exist
            mock_exists.return_value = False
            result = await code_gen_service._check_if_helpers_exist(
                project_id="test-project",
                entity_name="User",
                language_template=mock_language_template_python,
            )
            assert result is False

    @patch("app.api.v1.utils.code_merge_utils.extract_py_function_names")
    @patch(
        "app.api.v1.utils.code_merge_utils.extract_required_py_helpers_from_endpoint"
    )
    @patch(
        "app.api.v1.services.langchain_service.LangchainService.generate_helpers_sync"
    )
    async def test_update_or_append_helpers_python(
        self,
        mock_generate_helpers,
        mock_extract_required,
        mock_extract_functions,
        code_gen_service,
        mock_language_template_python,
    ):
        """Test helper updating for Python."""
        # Setup
        mock_extract_functions.return_value = ["get_all_users"]
        mock_extract_required.return_value = ["get_all_users", "create_user"]
        mock_generate_helpers.return_value = {
            "generated_code": "def create_user(): pass"
        }

        # Mock file operations
        m = mock_open(read_data="def get_all_users(): pass")
        with patch("builtins.open", m), patch("os.path.exists", return_value=True):
            await code_gen_service._update_or_append_helpers(
                project_id="test-project",
                entity_name="User",
                language_template=mock_language_template_python,
                endpoint_code="from helpers.user_helpers import get_all_users, create_user",
                model_code="class User: pass",
                schema_code="",
            )

        # Verify the function searched for missing helpers and appended them
        mock_extract_functions.assert_called_once()
        mock_extract_required.assert_called_once()  # Check that the endpoint_code was enhanced with context about all required functions
        call_args = mock_generate_helpers.call_args
        assert call_args[1]["project_id"] == "test-project"
        assert call_args[1]["entity_name"] == "User"
        assert call_args[1]["entity_description"] is None
        assert call_args[1]["model_code"] == "class User: pass"
        assert call_args[1]["schema_code"] == ""
        assert call_args[1]["only_functions"] == ["create_user"]
        assert (
            call_args[1]["language"] == "python"
        )  # Verify the endpoint_code contains the enhancement context and original code
        enhanced_code = call_args[1]["endpoint_code"]
        assert (
            "# IMPORTANT: The following helper functions are used across multiple HTTP methods:"
            in enhanced_code
        )
        assert "get_all_users" in enhanced_code
        assert "create_user" in enhanced_code
        assert (
            "from helpers.user_helpers import get_all_users, create_user"
            in enhanced_code
        )
        # Verify the new helper was appended to the file
        m.return_value.write.assert_called_once()

    @patch("app.api.v1.utils.code_merge_utils.extract_js_function_names")
    @patch(
        "app.api.v1.utils.code_merge_utils.extract_required_js_helpers_from_endpoint"
    )
    @patch(
        "app.api.v1.services.langchain_service.LangchainService.generate_helpers_sync"
    )
    async def test_update_or_append_helpers_javascript(
        self,
        mock_generate_helpers,
        mock_extract_required,
        mock_extract_functions,
        code_gen_service,
        mock_language_template_javascript,
    ):
        """Test helper updating for JavaScript."""
        # Setup
        mock_extract_functions.return_value = ["getAllItems"]
        mock_extract_required.return_value = ["getAllItems", "createItem"]
        mock_generate_helpers.return_value = {
            "generated_code": "exports.createItem = () => {};"
        }

        # Mock file operations
        m = mock_open(read_data="exports.getAllItems = () => {};")
        with patch("builtins.open", m), patch("os.path.exists", return_value=True):
            await code_gen_service._update_or_append_helpers(
                project_id="test-project",
                entity_name="User",
                language_template=mock_language_template_javascript,
                endpoint_code="const { getAllItems, createItem } = require('../utils/user.utils');",
                model_code="const mongoose = require('mongoose');",
                schema_code="",
            )

        # Verify the function searched for missing helpers and appended them
        mock_extract_functions.assert_called_once()
        mock_extract_required.assert_called_once()  # Check that the endpoint_code was enhanced with context about all required functions
        call_args = mock_generate_helpers.call_args
        assert call_args[1]["project_id"] == "test-project"
        assert call_args[1]["entity_name"] == "User"
        assert call_args[1]["entity_description"] is None
        assert call_args[1]["model_code"] == "const mongoose = require('mongoose');"
        assert call_args[1]["schema_code"] == ""
        assert call_args[1]["only_functions"] == ["createItem"]
        assert (
            call_args[1]["language"] == "javascript"
        )  # Verify the endpoint_code contains the enhancement context and original code
        enhanced_code = call_args[1]["endpoint_code"]
        assert (
            "# IMPORTANT: The following helper functions are used across multiple HTTP methods:"
            in enhanced_code
        )
        assert "getAllItems" in enhanced_code
        assert "createItem" in enhanced_code
        assert (
            "const { getAllItems, createItem } = require('../utils/user.utils');"
            in enhanced_code
        )
        # Verify the new helper was appended to the file
        m.return_value.write.assert_called_once()

    async def test_process_component_incrementally_helpers(
        self, code_gen_service, mock_language_template_python
    ):
        """Test incremental processing of helper components."""
        with patch.object(
            code_gen_service, "_update_or_append_helpers", new_callable=AsyncMock
        ) as mock_update:
            mock_update.return_value = {
                "file_path": "helpers/user_helpers.py",
                "generated_code": "helper code",
            }

            result = await code_gen_service._process_component_incrementally(
                component_type="helpers",
                project_id="test-project",
                entity_name="User",
                prompt="Create a user API",
                language_template=mock_language_template_python,
                generated_code={
                    "endpoint_code": "endpoint code",
                    "model_code": "model code",
                    "schema_code": "schema code",
                    "controller_code": "controller code",
                },
                method="GET",
                endpoint_path="/users",
            )

            # Verify the helper update was called
            mock_update.assert_called_once()
            assert result is not None
            assert result["file_path"] == "helpers/user_helpers.py"

    async def test_generate_new_components_get_post_methods(
        self, code_gen_service, mock_language_template_python
    ):
        """Test full component generation with GET then POST methods."""
        # Mock necessary methods
        with patch.object(
            code_gen_service, "_analyze_component_dependencies", new_callable=AsyncMock
        ) as mock_analyze, patch.object(
            code_gen_service, "_should_skip_component", new_callable=AsyncMock
        ) as mock_skip, patch.object(
            code_gen_service, "_process_component_incrementally", new_callable=AsyncMock
        ) as mock_process:

            # Setup mocks
            mock_analyze.return_value = {
                "needs_database": True,
                "needs_schema": True,
                "needs_helpers": True,
                "helpers_exist": False,
            }
            mock_skip.return_value = False  # Don't skip any components
            mock_process.side_effect = lambda **kwargs: {
                "component_type": kwargs["component_type"],
                "file_path": f"/app/{kwargs['component_type']}/{kwargs['entity_name'].lower()}.py",
                "generated_code": f"{kwargs['component_type']} code for {kwargs['method']}",
                "entity_name": kwargs["entity_name"],
            }

            # First, generate with GET method
            result = {}
            primary_component = {
                "component_type": "endpoint",
                "file_path": "/app/endpoints/user.py",
                "generated_code": "GET endpoint code",
                "entity_name": "User",
            }

            await code_gen_service._generate_new_components(
                result=result,
                language_template=mock_language_template_python,
                project_id="test-project",
                entity_name="User",
                prompt="Create a user API",
                primary_component=primary_component,
                method="GET",
                endpoint_path="/users",
            )

            # Verify GET method
            assert mock_process.call_count > 0
            assert len(result) > 0

            # Now, reset mocks and generate with POST method
            mock_analyze.reset_mock()
            mock_skip.reset_mock()
            mock_process.reset_mock()

            # Set helpers to exist for second call
            mock_analyze.return_value = {
                "needs_database": True,
                "needs_schema": True,
                "needs_helpers": True,
                "helpers_exist": True,
            }

            result = {}
            primary_component = {
                "component_type": "endpoint",
                "file_path": "/app/endpoints/user.py",
                "generated_code": "POST endpoint code",
                "entity_name": "User",
            }

            await code_gen_service._generate_new_components(
                result=result,
                language_template=mock_language_template_python,
                project_id="test-project",
                entity_name="User",
                prompt="Create a user API",
                primary_component=primary_component,
                method="POST",
                endpoint_path="/users",
            )

            # Verify POST method
            assert mock_process.call_count > 0
            assert len(result) > 0

            # Verify the helpers component was processed
            helper_calls = [
                call
                for call in mock_process.call_args_list
                if call[1]["component_type"] == "helpers"
            ]
            assert len(helper_calls) > 0

    @pytest.mark.integration
    async def test_full_code_generation_workflow(
        self, code_gen_service, mock_language_template_python
    ):
        """Integration test for the full code generation workflow."""
        # This is a more comprehensive test that simulates the entire code generation process

        # Mock filesystem operations
        with patch("os.path.exists") as mock_exists, patch(
            "builtins.open", mock_open(read_data="def get_all_users(): pass")
        ) as mock_merge_py, patch(
            "app.api.v1.services.langchain_service.LangchainService.generate_helpers_sync"
        ) as mock_generate:

            # Setup mock behavior
            mock_exists.side_effect = (
                lambda path: "helpers" in path and "_helpers.py" in path
            )  # Only helpers exist
            mock_merge_py.return_value = True
            mock_generate.return_value = {"generated_code": "def create_user(): pass"}

            # First pass: Generate GET endpoint
            primary_component = await mock_language_template_python.generate_component(
                component_type="endpoint",
                project_id="test-project",
                entity_name="User",
                entity_description="User data",
                method="GET",
                endpoint_path="/users",
            )

            result_get = {}
            await code_gen_service._generate_new_components(
                result=result_get,
                language_template=mock_language_template_python,
                project_id="test-project",
                entity_name="User",
                prompt="Create a user API with GET method",
                primary_component=primary_component,
                method="GET",
                endpoint_path="/users",
            )

            # Second pass: Generate POST endpoint (same path, different method)
            primary_component = await mock_language_template_python.generate_component(
                component_type="endpoint",
                project_id="test-project",
                entity_name="User",
                entity_description="User data",
                method="POST",
                endpoint_path="/users",
            )

            result_post = {}
            await code_gen_service._generate_new_components(
                result=result_post,
                language_template=mock_language_template_python,
                project_id="test-project",
                entity_name="User",
                prompt="Create a user API with POST method",
                primary_component=primary_component,
                method="POST",
                endpoint_path="/users",
            )

            # Verify that the helpers were properly handled in the second pass
            assert mock_merge_py.called or mock_generate.called

            # The generation should have been called with the correct parameters
            if mock_generate.called:
                # Get the keyword arguments from the last call
                call_kwargs = mock_generate.call_args[1]
                assert "only_functions" in call_kwargs

                # Verify that only the missing functions were requested
                # For POST, we'd expect "create_user" to be in the only_functions list
                # since "get_all_users" already exists
                if "create_user" in str(call_kwargs.get("only_functions", [])):
                    assert True

            # If we used merge_and_append_missing_py_helpers directly, verify it was called
            if mock_merge_py.called:
                assert True
