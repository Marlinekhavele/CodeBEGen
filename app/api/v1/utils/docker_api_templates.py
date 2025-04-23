
# API Documentation template
API_DOCS_GENERATION_TEMPLATE = """
You are an expert API documentation writer helping to document a backend API.
Generate comprehensive Markdown documentation for the following API:

Project ID: {project_id}
Entity Name: {entity_name}
HTTP Method: {method}
Endpoint Path: {endpoint_path}

CONTEXT PROVIDED:
Endpoint Code:
```python
{endpoint_code}

TASK: CREATE API DOCUMENTATION
Generate clear, detailed documentation for this API in Markdown format.
DOCUMENTATION REQUIREMENTS:

Title with Entity Name
Overview section
Base URL section
Endpoints section with:

HTTP method and path
Description
Request format
Response format with examples


Implementation details section

INCLUDE THE FOLLOWING ENDPOINTS:

The main endpoint defined in the code
The health check endpoint
Deployment endpoints:

POST /api/deploy
GET /api/deployment-status



FORMAT:
The documentation should follow this structure:
# [Entity Name] API Documentation

## Overview
[Brief description of what this API does]

## Base URL
`http://localhost:8000`

## Endpoints

### [METHOD] [PATH]
**Description**: [Description]
**Request Format**: [Format details]
**Response Format**: [Format details with example]

[Repeat for each endpoint]

## Implementation Details
[Brief implementation notes]
IMPORTANT:

Provide ONLY the Markdown documentation.
Use proper Markdown formatting.
Create useful and descriptive documentation that would help a developer understand how to use the API.
Include deployment endpoints and health check endpoint in addition to the main endpoint.
"""
DOCKERFILE_GENERATION_TEMPLATE = """
You are an expert Docker developer helping to containerize a backend application.
Generate a Dockerfile for the following project:
Project ID: {project_id}
Entity Name: {entity_name}
Language: {language}
TASK: CREATE DOCKERFILE
Generate a Dockerfile that properly containerizes a {language} application.
DOCKERFILE REQUIREMENTS:

Use an appropriate base image for {language}
Set up the working directory
Copy and install dependencies first (for build caching)
Copy application code
Run database migrations if applicable
Configure the appropriate command to start the application
Expose the correct port (8000)

LANGUAGE-SPECIFIC REQUIREMENTS:
For Python:

Use python:3.11-slim
Install requirements.txt
Run alembic migrations for database updates
Start with uvicorn for FastAPI

For JavaScript:

Use node:18-slim
Install dependencies from package.json
Run any needed migrations
Start with the appropriate command

EXPECTED OUTPUT:
A complete Dockerfile without explanations before or after.
IMPORTANT:

Return ONLY the Dockerfile content.
Do not include dockerfile or  markers.
Create a production-ready Dockerfile with best practices.
Keep the Dockerfile simple but complete.
"""