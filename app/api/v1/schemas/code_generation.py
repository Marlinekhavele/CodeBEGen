# app/api/v1/schemas/code_generation.py

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

class CodeGenerationRequest(BaseModel):
    """Schema for code generation requests"""
    project_id: str = Field(..., description="Project identifier")
    prompt: str = Field(..., description="Natural language description of what to generate")
    language: Optional[str] = Field("python", description="Programming language: python, javascript, etc.")
    
    # Optional fields for endpoint generation
    method: Optional[str] = Field(None, description="HTTP method for endpoint generation")
    endpoint_path: Optional[str] = Field(None, description="Path for endpoint generation")
    additional_context: Optional[str] = Field(None, description="Additional context for generation")
    
    # For advanced usage only - most users won't need these
    # entity_name: Optional[str] = Field(None, description="Entity name if known")
    # should_generate_model: Optional[bool] = Field(None, description="Override auto-detection for model generation")
    # should_generate_schema: Optional[bool] = Field(None, description="Override auto-detection for schema generation")
    # should_generate_helpers: Optional[bool] = Field(None, description="Override auto-detection for helpers generation")
    
    class Config:
        schema_extra = {
            "example": {
                "project_id": "my-project",
                "prompt": "Create an endpoint to manage users with name and email fields",
                "language": "python",
                "method": "POST",
                "endpoint_path": "/api/v1/users"
            }
        }

class GeneratedArtifact(BaseModel):
    """Schema for a single generated code artifact"""
    file_path: str = Field(..., description="Path where the file should be saved")
    generated_code: str = Field(..., description="Generated code content")
    content_base64: str = Field(..., description="Base64-encoded content")
    file_hash: str = Field(..., description="Hash of the file content")

class GenerationResult(BaseModel):
    """Schema for the generation result content"""
    endpoint: Optional[GeneratedArtifact] = Field(None, description="Generated endpoint code")
    model: Optional[GeneratedArtifact] = Field(None, description="Generated model code")
    schema: Optional[GeneratedArtifact] = Field(None, description="Generated schema code")
    helpers: Optional[GeneratedArtifact] = Field(None, description="Generated helper functions")
    
    # Metadata
    entity_name: Optional[str] = Field(None, description="Detected or specified entity name")
    detected_database_usage: Optional[bool] = Field(None, description="Whether database usage was detected")
    language: str = Field(..., description="Programming language of the generated code")
    file_extension: str = Field(..., description="File extension for the language")
    
    class Config:
        schema_extra = {
            "example": {
                "endpoint": {
                    "file_path": "routes/users.js",
                    "generated_code": "const express = require('express');...",
                    "content_base64": "Y29uc3QgZXhwcmVzcyA9IHJlcXVpcmUoJ2V4cHJlc3MnKTsuLi4=",
                    "file_hash": "a1b2c3d4e5f6..."
                },
                "model": {
                    "file_path": "models/user.js",
                    "generated_code": "const mongoose = require('mongoose');...",
                    "content_base64": "Y29uc3QgbW9uZ29vc2UgPSByZXF1aXJlKCdtb25nb29zZScpOy4uLg==",
                    "file_hash": "f6e5d4c3b2a1..."
                },
                "entity_name": "User",
                "detected_database_usage": True,
                "language": "javascript",
                "file_extension": ".js"
            }
        }

class CodeGenerationResponse(BaseModel):
    """Schema for code generation responses"""
    success: bool = Field(..., description="Whether the generation was successful")
    message: str = Field(..., description="Status message")
    result: Optional[GenerationResult] = Field(None, description="Generated code result")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Code generation successful",
                "result": {
                    "endpoint": {
                        "file_path": "routes/users.js",
                        "generated_code": "const express = require('express');...",
                        "content_base64": "Y29uc3QgZXhwcmVzcyA9IHJlcXVpcmUoJ2V4cHJlc3MnKTsuLi4=",
                        "file_hash": "a1b2c3d4e5f6..."
                    },
                    "model": {
                        "file_path": "models/user.js",
                        "generated_code": "const mongoose = require('mongoose');...",
                        "content_base64": "Y29uc3QgbW9uZ29vc2UgPSByZXF1aXJlKCdtb25nb29zZScpOy4uLg==",
                        "file_hash": "f6e5d4c3b2a1..."
                    },
                    "entity_name": "User",
                    "detected_database_usage": True,
                    "language": "javascript",
                    "file_extension": ".js"
                }
            }
        }