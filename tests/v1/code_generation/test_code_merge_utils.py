from unittest.mock import mock_open, patch

import pytest

from app.api.v1.utils.code_merge_utils import (
    extract_js_function_names,
    extract_py_function_names,
    extract_required_js_helpers_from_endpoint,
    extract_required_py_helpers_from_endpoint,
    merge_and_append_missing_js_helpers,
    merge_and_append_missing_py_helpers,
)


class TestCodeMergeUtils:
    """Test suite for code merge utility functions."""

    def test_extract_py_function_names(self):
        """Test extracting Python function names."""
        code = """
def get_all_users():
    return []

def get_user_by_id(user_id):
    return {"id": user_id}

def create_user(user_data):
    return {"id": 1, **user_data}
"""
        functions = extract_py_function_names(code)
        assert "get_all_users" in functions
        assert "get_user_by_id" in functions
        assert "create_user" in functions
        assert len(functions) == 3

    def test_extract_js_function_names(self):
        """Test extracting JavaScript function names."""
        code = """
function getAllUsers() {
    return [];
}

const getUserById = (userId) => {
    return { id: userId };
};

exports.createUser = (userData) => {
    return { id: 1, ...userData };
};

module.exports = {
    getAllUsers,
    getUserById,
    createUser
};
"""
        functions = extract_js_function_names(code)
        assert "getAllUsers" in functions
        assert "getUserById" in functions
        assert "createUser" in functions
        assert len(functions) == 3

    def test_extract_required_py_helpers_from_endpoint(self):
        """Test extracting required Python helper functions from an endpoint."""
        code = """
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from helpers.user_helpers import get_all_users, get_user_by_id
from database import get_db

router = APIRouter()

@router.get("/users")
def read_users(db: Session = Depends(get_db)):
    return get_all_users(db)

@router.get("/users/{user_id}")
def read_user(user_id: int, db: Session = Depends(get_db)):
    return get_user_by_id(user_id, db)

@router.post("/users")
def create_user(user_data: dict, db: Session = Depends(get_db)):
    # Function not imported but used
    return create_user(user_data, db)
"""
        required_functions = extract_required_py_helpers_from_endpoint(code)
        assert "get_all_users" in required_functions
        assert "get_user_by_id" in required_functions
        assert (
            "create_user" in required_functions
        )  # Should detect function calls even if not imported

    def test_extract_required_js_helpers_from_endpoint(self):
        """Test extracting required JavaScript helper functions from an endpoint."""
        code = """
const express = require('express');
const router = express.Router();
const { getAllUsers, getUserById } = require('../utils/user.utils');

router.get('/users', (req, res) => {
    const users = getAllUsers();
    res.json(users);
});

router.get('/users/:id', (req, res) => {
    const user = getUserById(req.params.id);
    res.json(user);
});

router.post('/users', (req, res) => {
    // Function not imported but used
    const newUser = createUser(req.body);
    res.status(201).json(newUser);
});

module.exports = router;
"""
        required_functions = extract_required_js_helpers_from_endpoint(code)
        assert "getAllUsers" in required_functions
        assert "getUserById" in required_functions
        assert (
            "createUser" in required_functions
        )  # Should detect function calls even if not imported

    @pytest.mark.asyncio
    @patch(
        "app.api.v1.services.langchain_service.LangchainService.generate_helpers_sync"
    )
    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists")
    async def test_merge_and_append_missing_py_helpers(
        self, mock_exists, mock_file, mock_generate
    ):
        """Test merging and appending missing Python helper functions."""
        # Setup
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = """
def get_all_users(db):
    return db.query(User).all()
"""
        mock_generate.return_value = {
            "generated_code": """
def get_user_by_id(user_id, db):
    return db.query(User).filter(User.id == user_id).first()

def create_user(user_data, db):
    user = User(**user_data)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
"""
        }

        # Test with endpoint that requires all three functions
        endpoint_code = """
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from helpers.user_helpers import get_all_users, get_user_by_id, create_user

router = APIRouter()

@router.get("/users")
def read_users(db: Session = Depends(get_db)):
    return get_all_users(db)

@router.get("/users/{user_id}")
def read_user(user_id: int, db: Session = Depends(get_db)):
    return get_user_by_id(user_id, db)

@router.post("/users")
def create_user_endpoint(user_data: dict, db: Session = Depends(get_db)):
    return create_user(user_data, db)
"""

        # Call merge function
        result = await merge_and_append_missing_py_helpers(
            helpers_file_path="helpers/user_helpers.py",
            endpoint_code=endpoint_code,
            model_code="class User: pass",
            schema_code="",
            entity_name="User",
            entity_description="User entity",
            project_id="test-project",
        )

        # Verify
        assert result is True
        mock_generate.assert_called_once()

        # Check that correct functions were requested
        call_kwargs = mock_generate.call_args[1]
        assert "only_functions" in call_kwargs
        only_functions = call_kwargs["only_functions"]
        assert "get_user_by_id" in only_functions
        assert "create_user" in only_functions
        assert "get_all_users" not in only_functions  # Already exists

        # Verify file was opened and appended
        mock_file.return_value.write.assert_called_once()

    @pytest.mark.asyncio
    @patch(
        "app.api.v1.services.langchain_service.LangchainService.generate_helpers_sync"
    )
    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists")
    async def test_merge_and_append_missing_js_helpers(
        self, mock_exists, mock_file, mock_generate
    ):
        """Test merging and appending missing JavaScript helper functions."""
        # Setup
        mock_exists.return_value = True
        mock_file.return_value.read.return_value = """
exports.getAllUsers = () => {
    return User.find();
};
"""
        mock_generate.return_value = {
            "generated_code": """
exports.getUserById = (userId) => {
    return User.findById(userId);
};

exports.createUser = (userData) => {
    const user = new User(userData);
    return user.save();
};
"""
        }

        # Test with endpoint that requires all three functions
        endpoint_code = """
const express = require('express');
const router = express.Router();
const { getAllUsers, getUserById, createUser } = require('../utils/user.utils');

router.get('/users', (req, res) => {
    const users = getAllUsers();
    res.json(users);
});

router.get('/users/:id', (req, res) => {
    const user = getUserById(req.params.id);
    res.json(user);
});

router.post('/users', (req, res) => {
    const newUser = createUser(req.body);
    res.status(201).json(newUser);
});

module.exports = router;
"""

        # Call merge function
        result = await merge_and_append_missing_js_helpers(
            helpers_file_path="/app/utils/user.utils.js",
            endpoint_code=endpoint_code,
            model_code="const mongoose = require('mongoose');",
            schema_code="",
            entity_name="User",
            entity_description="User entity",
            project_id="test-project",
        )  # Verify
        assert result is True
        mock_generate.assert_called_once()

        # Check that correct functions were requested
        call_kwargs = mock_generate.call_args[1]
        assert "only_functions" in call_kwargs
        only_functions = call_kwargs["only_functions"]
        assert "getUserById" in only_functions
        assert "createUser" in only_functions
        assert "getAllUsers" not in only_functions  # Already exists

        # Verify file was opened and appended
        mock_file.return_value.write.assert_called_once()
