import json
import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1.services.model_schema_update.model_schema_manager import ModelSchemaManager
from app.api.v1.utils.prompt_manager import PromptManager


@pytest.fixture
def temp_project_dir():
    with tempfile.TemporaryDirectory() as tmpdirname:
        original_dir = os.getcwd()
        os.chdir(tmpdirname)
        yield tmpdirname
        os.chdir(original_dir)


@pytest.fixture
def sample_model_code():
    return """
from sqlalchemy import Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String(100), nullable=False)
    name = Column(String(100))
"""


MOCK_CHANGES = [
    {
        "type": "add",
        "field_name": "password",
        "definition": "Column(String(100), nullable=False)",
    },
    {"type": "rename", "field_name": "email", "new_name": "email_address"},
]

MOCK_CHANGES_JSON = json.dumps(MOCK_CHANGES)


@pytest.mark.asyncio
class TestModelSchemaManager:

    async def test_analyze_required_changes_success(self, sample_model_code):
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = json.dumps(MOCK_CHANGES)

        with patch(
            "app.api.v1.services.langchain_service.LangchainService.create_chain_from_template",
            return_value=mock_chain,
        ), patch(
            "app.api.v1.services.langchain_service.LangchainService.clean_code",
            return_value=json.dumps(MOCK_CHANGES),
        ), patch.object(
            ModelSchemaManager,
            "_clean_json_response",
            return_value=json.dumps(MOCK_CHANGES),
        ), patch.object(
            PromptManager,
            "format_template",
            return_value="mock_formatted_template"
        ):

            prompt = (
                "Add a password field as String(100) and rename email to email_address"
            )
            changes = await ModelSchemaManager.analyze_required_changes(
                prompt_description=prompt,
                entity_name="User",
                existing_model_code=sample_model_code,
                language="python",
            )

            assert len(changes) == 2
            assert changes[0]["type"] == "add"
            assert changes[0]["field_name"] == "password"
            assert changes[1]["type"] == "rename"
            assert changes[1]["field_name"] == "email"

    async def test_analyze_required_changes_invalid_prompt(self, sample_model_code):
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = "[]"

        with patch(
            "app.api.v1.services.langchain_service.LangchainService.create_chain_from_template",
            return_value=mock_chain,
        ), patch(
            "app.api.v1.services.langchain_service.LangchainService.clean_code",
            return_value="[]",
        ), patch.object(
            ModelSchemaManager, "_clean_json_response", return_value="[]"
        ), patch.object(
            PromptManager,
            "format_template",
            return_value="mock_formatted_template"
        ):

            prompt = ""
            changes = await ModelSchemaManager.analyze_required_changes(
                prompt_description=prompt,
                entity_name="User",
                existing_model_code=sample_model_code,
                language="python",
            )

            assert len(changes) == 0

    async def test_process_model_changes_invalid_path(self):
        with patch(
            "app.api.v1.services.project_analysis_service.ProjectAnalysisService.analyze_project"
        ) as mock_analyze:
            mock_analyze.return_value = {"models": []}

            result = await ModelSchemaManager.process_model_changes(
                project_id="nonexistent",
                entity_name="InvalidModel",
                prompt_description="Add a field",
                generate_migration=True,
            )

            assert "error" in result
            assert "Model InvalidModel not found in project" in result["error"]
            assert result["model_updated"] is False

    async def test_schema_validation_error(self, temp_project_dir):
        with patch(
            "app.api.v1.services.project_analysis_service.ProjectAnalysisService.analyze_project"
        ) as mock_analyze:
            mock_analyze.return_value = {
                "models": [{"name": "User", "file": "user.py"}]
            }

            with patch.object(
                ModelSchemaManager, "analyze_required_changes"
            ) as mock_changes:
                mock_changes.return_value = [
                    {
                        "type": "invalid_type",
                        "field_name": "test",
                        "definition": "Invalid",
                    }
                ]

                os.makedirs(
                    os.path.join(temp_project_dir, "repos", "test-project", "models"),
                    exist_ok=True,
                )
                model_file_path = os.path.join(
                    temp_project_dir, "repos", "test-project", "models", "user.py"
                )
                with open(model_file_path, "w") as f:
                    f.write("class User:\n    pass")

                with patch.object(
                    ModelSchemaManager, "_update_model_file"
                ) as mock_update:
                    mock_update.side_effect = ValueError(
                        "Invalid change type: invalid_type"
                    )

                    result = await ModelSchemaManager.process_model_changes(
                        project_id="test-project",
                        entity_name="User",
                        prompt_description="Invalid change",
                        generate_migration=True,
                    )

                    assert "error" in result
                    assert "Invalid change type: invalid_type" in result["error"]
                    assert result["model_updated"] is False

    async def test_concurrent_changes(self, sample_model_code):
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = json.dumps(MOCK_CHANGES)

        with patch(
            "app.api.v1.services.langchain_service.LangchainService.create_chain_from_template",
            return_value=mock_chain,
        ), patch(
            "app.api.v1.services.langchain_service.LangchainService.clean_code",
            return_value=json.dumps(MOCK_CHANGES),
        ), patch.object(
            ModelSchemaManager,
            "_clean_json_response",
            return_value=json.dumps(MOCK_CHANGES),
        ), patch.object(
            PromptManager,
            "format_template",
            return_value="mock_formatted_template"
        ):

            import asyncio

            tasks = [
                ModelSchemaManager.analyze_required_changes(
                    prompt_description=f"Add field_{i}",
                    entity_name="User",
                    existing_model_code=sample_model_code,
                    language="python",
                )
                for i in range(3)
            ]

            results = await asyncio.gather(*tasks)
            assert len(results) == 3
            for result in results:
                assert isinstance(result, list)
                assert len(result) == 2