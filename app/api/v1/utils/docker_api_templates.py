# Enhanced API Documentation template for comprehensive testing-focused docs
API_DOCS_GENERATION_TEMPLATE = """
You are an expert API documentation writer helping to document a backend API with focus on testing and usability.
Generate comprehensive Markdown documentation for the following API:

Project ID: {project_id}
Entity Name: {entity_name}
HTTP Method: {method}
Endpoint Path: {endpoint_path}

CONTEXT PROVIDED:
Endpoint Code:
```{language}
{endpoint_code}
```

Schema Code (for request/response examples):
```{language}
{schema_code}
```

Model Code (for field structure):
```{language}
{model_code}
```

TASK: CREATE COMPREHENSIVE API DOCUMENTATION
Generate clear, detailed documentation for this API in Markdown format that helps developers understand and test the endpoints.

DOCUMENTATION REQUIREMENTS:

1. **Entity-focused Title and Overview**
2. **Base URL and Authentication** (if applicable)
3. **Comprehensive Endpoints Documentation** including:
   - HTTP method and path
   - Description and purpose
   - Request format with realistic examples
   - Response format with success and error examples
   - HTTP status codes
4. **Testing Guide** with step-by-step instructions
5. **Error Handling** documentation

ENDPOINT ANALYSIS RULES:
- Analyze the endpoint code to extract the actual implemented endpoints
- Generate request examples based on the schema code structure
- Create response examples based on the model/schema definitions
- **EXCLUDE deployment-related endpoints** (deploy, deployment-status)
- **EXCLUDE internal/system endpoints** unless they're part of the main API
- Focus on the business logic endpoints for the specific entity

FORMAT:
Generate documentation following this structure:

# {entity_name} API Documentation

## Overview
[Description based on entity purpose and endpoint functionality]

## Base URL
```
http://localhost:8000
```

## Authentication
[If authentication is detected in the code, document it; otherwise, state "No authentication required"]

## Endpoints

### [HTTP_METHOD] [ENDPOINT_PATH]
**Description**: [What this endpoint does]

**Query Parameters**:
- List each query parameter in this format:
  - **parameter_name** (type, optional/required): Description
- Example:
  - **name** (string, optional): Filter books by name.
  - **isbn** (string, optional): Filter books by ISBN.
  - **author** (string, optional): Filter books by author.
  - **title** (string, optional): Filter books by title.
  - **id** (integer, optional): Filter books by ID.

**Request Format**:
```json
[Realistic JSON example based on schema/model]
```

**Success Response** (200/201):
```json
[JSON response example based on schema/model]
```

**Error Responses**:
- **400 Bad Request**: Invalid input data
- **404 Not Found**: Resource not found
- **500 Internal Server Error**: Server error

**Status Codes**:
- 200 - Success (GET, PUT, PATCH)
- 201 - Created (POST)
- 204 - No Content (DELETE)
- 400 - Bad Request
- 404 - Not Found
- 500 - Internal Server Error

### Health Check
**GET** `/health`
Simple health check endpoint.

**Response**:
```json
{
  "status": "healthy",
  "message": "API is running"
}
```

## Testing Guide

### Using the Test Tab
To test these endpoints using the built-in testing interface:

1. **Navigate to the Test tab** in your API testing tool
2. **Select the HTTP method** (GET, POST, PUT, DELETE)
3. **Enter the endpoint URL:**
   ```
   http://localhost:8000[endpoint_path]
   ```
4. **Add request headers** (if required):
   ```json
   {
     "Content-Type": "application/json"
   }
   ```
5. **Add request body** (for POST/PUT/PATCH):
   [Include specific JSON examples for each endpoint]

### Example Test Requests

[Generate specific test examples for each endpoint found in the code]

## Error Handling

All endpoints return structured error responses:

```json
{
  "status_code": 400,
  "status": false,
  "message": "Error description",
  "detail": "Additional error details"
}
```

## Implementation Notes
[Brief notes about the API implementation, database usage, etc.]

IMPORTANT INSTRUCTIONS:
- Generate ONLY the Markdown documentation
- Use proper Markdown formatting
- Create realistic, useful examples based on the provided schema/model code
- Focus on testing usability
- Exclude deployment and internal system endpoints
- Include comprehensive testing instructions
- Ensure all JSON examples are valid and realistic
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
