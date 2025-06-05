# Prompt templates for the step-by-step code generation
# Step 1: Generate the FastAPI endpoint only
ENDPOINT_GENERATION_TEMPLATE = """
You are an expert FastAPI developer helping to create an endpoint for a CodeBeGen project.
Generate a FastAPI endpoint based on the following description:
Description: {endpoint_description}
HTTP Method: {method}
Endpoint Path: {endpoint_path}
PROJECT CONTEXT:
{additional_context}

# RELATED ENDPOINTS CONTEXT
{related_endpoints}

# SIMILAR ENDPOINTS CONTEXT
{similar_endpoints}

# TASK: CREATE ENDPOINT ONLY
Your task is to generate a FastAPI endpoint that implements the described functionality based on the description and context.
Internally identify the main data entity (e.g., 'User', 'Product', 'Order') to ensure correct imports and helper function usage, but DO NOT explicitly state it in the output.

# OUTPUT FORMAT:
Provide ONLY the Python code for the endpoint.

Example Output Structure:
```python
from fastapi import APIRouter
# ... other imports ...

router = APIRouter()

@router.get("/example")
async def example_endpoint():
    # ... endpoint logic ...
    return {{"message": "success"}}

```

# METHOD-CENTRIC RULES
1. **Strict Method Adherence**:
   - Only implement @router.{method_lower} decorators
   - Use proper FastAPI parameter handling for {method}
2. **Response Requirements**:
   - Include appropriate status codes (200 for GET, 201 for POST, etc.)
   - Return structured JSON responses
   - Always include a proper response_model for GET endpoints
   - **CRITICAL**: For response_model, ALWAYS use EntitySchema, NEVER just Entity (e.g., use TodoSchema, not Todo)
3. **Import Requirements**:
   - **CRITICAL**: Include ALL necessary imports based on what you actually use in the code
   - **FastAPI Core Imports**: Always import what you use from fastapi:
     - `APIRouter` - ALWAYS required for router = APIRouter()
     - `Depends` - REQUIRED when using dependency injection (e.g., `db: Session = Depends(get_db)`)
     - `HTTPException` - REQUIRED when raising HTTP exceptions (e.g., `raise HTTPException(status_code=404, ...)`)
     - `status` - REQUIRED when using status codes (e.g., `status.HTTP_201_CREATED`, `status_code=status.HTTP_404_NOT_FOUND`)
     - `Query`, `Path`, `Body` - REQUIRED when using these parameter types
   - **Typing Imports**: Import from `typing` module when used:
     - `List` - REQUIRED for endpoints returning multiple items (e.g., `response_model=List[BookSchema]`)
     - `Optional`, `Dict`, `Any` - REQUIRED when used in type hints   - **Database-related Imports** (REQUIRED when endpoint uses database/Session):
     - **CRITICAL**: Import the model: `from models.book import Book` (Replace 'book' with the actual entity) - ALWAYS REQUIRED when using database sessions
     - **CRITICAL**: Import the schema: `from schemas.book import BookSchema, BookCreate` (Replace 'book' with the actual entity) - ALWAYS REQUIRED for database endpoints
     - **CRITICAL**: ALWAYS use EntitySchema naming pattern (e.g., TodoSchema, ProductSchema, UserSchema). NEVER use just Entity (e.g., Todo, Product, User).
     - **CRITICAL**: Import the helpers: `from helpers.book_helpers import get_all_books, get_book_by_id` (Replace 'book' with the actual entity) - ALWAYS REQUIRED when calling helper functions
     - **CRITICAL**: Import database session and dependency: `from sqlalchemy.orm import Session` and `from core.database import get_db` - ALWAYS REQUIRED when using `db: Session = Depends(get_db)`
     - **CRITICAL**: Use dependency injection for the session: `db: Session = Depends(get_db)` in the function signature for ALL database endpoints.
   - **Import Logic**: If you use ANY function, class, or constant in your code, you MUST import it. Never use undefined imports.
   - If the endpoint is NOT database-dependent, do NOT import database modules (`Session`, `get_db`, models, schemas, helpers requiring db).
   - Always import `List` from `typing` for GET/POST endpoints returning multiple items.
4. **Helper Functions**:
   - Assume there are helper functions available in `helpers/[entity]_helpers.py`
   - Use these helper functions in your implementation instead of direct queries when appropriate
   - For database endpoints: use `get_all_books(db)` instead of `db.query(Book).all()`
   - For non-database endpoints: use appropriate utility functions without database parameters
   - **CRITICAL**: Every helper function you call in your endpoint code MUST be imported. If you use `get_book_by_id(db, book_id)`, you MUST import `get_book_by_id` from the helpers module.
   - **CRITICAL**: If you use `create_book(db=db, book=book)`, you MUST import `create_book` from the helpers module.
   - **CRITICAL**: If you use `update_book(db, book_id, book_data)`, you MUST import `update_book` from the helpers module.
   - **CRITICAL**: If you use `delete_book(db, book_id)`, you MUST import `delete_book` from the helpers module.

# CRITICAL NAMING INSTRUCTION:
# The schema class names you import (e.g., `from schemas.product import ProductSchema`)
# and helper function names you call (e.g., `from helpers.product_helpers import get_product`)
# WILL DICTATE the exact names that *must* be implemented in subsequent generation steps.
# Use clear, conventional names based on the inferred entity (e.g., `ProductSchema`, `ProductCreate`, `get_all_products`, `create_product`).
# CRITICAL: ALWAYS use the EntitySchema naming pattern for response models (e.g., TodoSchema, ProductSchema, UserSchema).
# NEVER use just the entity name (e.g., Todo, Product, User) for schema imports or response_model declarations.

# CRITICAL DATABASE IMPORT RULE:
# **IF YOUR ENDPOINT USES A DATABASE SESSION (`db: Session = Depends(get_db)`), YOU MUST:**
# 1. Import the model: `from models.[entity] import [Entity]` (e.g., `from models.book import Book`)
# 2. Import the schema: `from schemas.[entity] import [Entity]Schema, [Entity]Create` (e.g., `from schemas.book import BookSchema, BookCreate`)
# 3. Import helper functions: `from helpers.[entity]_helpers import [functions]` (e.g., `from helpers.book_helpers import get_all_books, create_book`)
# 4. Import database dependencies: `from sqlalchemy.orm import Session` and `from core.database import get_db`
#
# **NO DATABASE SESSION = NO MODEL IMPORTS NEEDED**
# **DATABASE SESSION PRESENT = MODEL IMPORTS MANDATORY**

# IMPORT-USAGE CONSISTENCY RULE:
# BEFORE writing your imports, first write your endpoint logic, then identify ALL functions you use.
# Your import statements must include EVERY helper function you call in your code.
# Common helper function patterns:
# - get_all_[entity_plural](db) → must import get_all_[entity_plural]
# - get_[entity]_by_id(db, id) → must import get_[entity]_by_id
# - create_[entity](db, data) → must import create_[entity]
# - update_[entity](db, id, data) → must import update_[entity]
# - delete_[entity](db, id) → must import delete_[entity]

# IMPORT MAPPING - ALWAYS USE THESE PATTERNS:
When your code contains these patterns, you MUST include these imports:

**FastAPI Components:**
- `router = APIRouter()` → `from fastapi import APIRouter`
- `Depends(get_db)` → `from fastapi import Depends`
- `raise HTTPException(...)` → `from fastapi import HTTPException`
- `status.HTTP_*` or `status_code=status.HTTP_*` → `from fastapi import status`
- `Query(...)`, `Path(...)`, `Body(...)` → `from fastapi import Query, Path, Body`

**Typing Components:**
- `List[SomeType]` → `from typing import List`
- `Optional[SomeType]` → `from typing import Optional`
- `Dict[str, Any]` → `from typing import Dict, Any`

**Database Components:**
- `Session` type hint → `from sqlalchemy.orm import Session`
- `get_db` function → `from core.database import get_db`
- **CRITICAL**: `db: Session = Depends(get_db)` → MUST import `from models.[entity] import [Entity]` (e.g., `from models.book import Book`)
- **CRITICAL**: ANY database endpoint → MUST import the model class (e.g., `from models.book import Book`)

**Status Code Examples:**
- `status_code=200` → Use `status_code=200` (no import needed)
- `status_code=status.HTTP_201_CREATED` → `from fastapi import status`
- `status_code=status.HTTP_404_NOT_FOUND` → `from fastapi import status`

**Error Handling Examples:**
- `raise HTTPException(status_code=404, detail="Not found")` → `from fastapi import HTTPException`
- `raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bad request")` → `from fastapi import HTTPException, status`

**Schema Import Examples:**
- `response_model=TodoSchema` → `from schemas.todo import TodoSchema`
- `response_model=List[ProductSchema]` → `from schemas.product import ProductSchema` and `from typing import List`
- NEVER use `from schemas.todo import Todo` - ALWAYS use `from schemas.todo import TodoSchema`

# --- ILLUSTRATIVE EXAMPLE ---
The following code examples demonstrate the expected structure and principles.
Adapt these principles to the specific requirements of the current request. Do NOT simply copy the example code.

# CODE EXAMPLE
## Database-dependent endpoint:
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session  # Import Session
from typing import List
from core.database import get_db  # Import get_db
from models.book import Book
from schemas.book import BookSchema, BookCreate
from helpers.book_helpers import get_all_books, get_book_by_id, create_book  # Import ALL helper functions used in the code

router = APIRouter()

@router.get("/books", status_code=200, response_model=List[BookSchema])
async def get_books(
    db: Session = Depends(get_db)  # Use Depends(get_db)
):
    \"\"\"Get all books\"\"\"
    # Use helper function instead of direct query, passing the db session
    books = get_all_books(db)
    return books

@router.get("/books/{book_id}", status_code=200, response_model=BookSchema)
async def get_book(
    book_id: int,
    db: Session = Depends(get_db)
):
    \"\"\"Get book by ID\"\"\"
    book = get_book_by_id(db, book_id)  # This function is imported above
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book

@router.post("/books", status_code=status.HTTP_201_CREATED, response_model=BookSchema)
async def create_new_book(
    book: BookCreate,
    db: Session = Depends(get_db) # Use Depends(get_db)
):
    \"\"\"Create a new book\"\"\"
    # Pass db session to the helper function
    new_book = create_book(db=db, book=book)  # This function is imported above
    if not new_book: # Example error handling if helper indicates failure
        raise HTTPException(status_code=400, detail="Book could not be created")
    return new_book
```
## Non-database dependent endpoint:
```python
from fastapi import APIRouter, status
from typing import Dict, Any
from helpers.health_helpers import check_system_status
router = APIRouter()
@router.get("/health", status_code=200)
async def health_check():
    \"\"\"Check system health status\"\"\"
    status_info = check_system_status()
    return status_info
```
IMPORTANT:
1. Return ONLY the Python code for the endpoint.
2. Assume models, schemas, and helper functions for the relevant entity/entities will be generated in other steps or already exist.
3. Do not include any explanations, comments, or text before or after the code block itself.
4. **CRITICAL - COMPLETE IMPORTS**: ALWAYS include ALL necessary imports for ANY function, class, constant, or module you use in the code:
   - `from fastapi import APIRouter` - ALWAYS required
   - `from core.database import get_db` - REQUIRED when using `Depends(get_db)`
   - `from fastapi import Depends` - REQUIRED when using `Depends(get_db)`
   - `from fastapi import HTTPException` - REQUIRED when using `raise HTTPException(...)`
   - `from fastapi import status` - REQUIRED when using `status.HTTP_*` constants
   - `from typing import List` - REQUIRED when using `List[SomeType]`
   - Any other imports based on what you actually use in the code
5. ALWAYS use helper functions (e.g., `get_all_<entity_plural>(db)`) in your implementation when appropriate, inferring the entity name from the description and passing the `db` session if required.
6. For GET requests returning multiple items, use `response_model=List[<EntitySchema>]`.
7. Always remove the ```python ``` markdown from the start and end of the code block itself.
8. ONLY include database imports (`core.database.get_db`, `sqlalchemy.orm.Session`, models, schemas, db-dependent helpers) for endpoints that need database access based on the description. Ensure `db: Session = Depends(get_db)` is used in the function signature for these endpoints.
9. **ERROR HANDLING**: When implementing error handling (e.g., checking if a resource exists), ALWAYS import `HTTPException` and use appropriate status codes.
10. **SPECIFIC PATTERNS TO WATCH FOR**:
    - If you write `raise HTTPException(...)` → MUST import `from fastapi import HTTPException`
    - If you write `status.HTTP_*` → MUST import `from fastapi import status`
    - If you write `List[...]` → MUST import `from typing import List`
    - If you write `Depends(...)` → MUST import `from fastapi import Depends`
    - If you write `db: Session` → MUST import `from sqlalchemy.orm import Session`
    - If you write `db: Session = Depends(get_db)` → MUST import `from core.database import get_db`
    - **CRITICAL**: If you write `db: Session = Depends(get_db)` → MUST ALSO import the model: `from models.[entity] import [Entity]`
11. **FUNCTION-IMPORT CONSISTENCY CHECK**:
    - Before finalizing your code, scan through ALL function calls in your endpoint logic
    - For EVERY helper function you call (e.g., `get_book_by_id`, `create_book`, `update_book`, `delete_book`), ensure it's included in your import statement
    - For EVERY helper function you call (e.g., `get_book_by_id`, `create_book`, `update_book`, `delete_book`), ensure it's included in your import statement
    - Example: If your code contains `existing_book = get_book_by_id(db, book_id)`, your imports MUST include:
      ```python
      from helpers.book_helpers import get_all_books, get_book_by_id, create_book
      ```
    - Example: If your code contains `new_item = create_item(db=db, item=item_data)`, your imports MUST include:
      ```python
      from helpers.item_helpers import create_item
      ```
12. **FINAL VERIFICATION**: After writing your endpoint code, review ALL function calls and ensure each has a corresponding import. This is the most common source of import errors.
13. **DATABASE SESSION VERIFICATION**:
    - **CRITICAL**: If your endpoint has `db: Session = Depends(get_db)`, you MUST import the model class (e.g., `from models.book import Book`)
    - **CRITICAL**: If your endpoint has `db: Session = Depends(get_db)`, you MUST import the schema classes (e.g., `from schemas.book import BookSchema, BookCreate`)
    - **CRITICAL**: Database endpoints without model imports will cause runtime errors
"""

# Step 2: Generate the SQLAlchemy model
MODEL_GENERATION_TEMPLATE = """
You are an expert SQLAlchemy developer helping to create a database model.
Generate a SQLAlchemy model for the following entity:
Entity Name: {entity_name}
Entity Description: {entity_description}

CONTEXT PROVIDED (Optional Reference):
The following endpoint code was generated in a previous step.
You can use it for context if helpful, but prioritize the Entity Name and Description for model structure.
Endpoint Code:
```python
{endpoint_code}
```

# TASK: CREATE DATABASE MODEL ONLY
Your task is to create a SQLAlchemy model for this entity that will work with FastAPI and Alembic migrations.
# MODEL REQUIREMENTS
1. **Base Structure**:
   - Extend Base class from core.database import Base
   - Include a primary key named 'id' (preferably using UUID)
   - Add created_at and updated_at timestamps

2. **Column Types**:
   - Use appropriate SQLAlchemy Column types
   - Include nullable, unique, index constraints as needed
   - Add relationships to other models if necessary
   - ALWAYS import ANY type you use (SQLAlchemy types, Python modules, etc.)
   - If you use Boolean, Integer, DateTime, ForeignKey, UUID, or any other type, ALWAYS import it explicitly in the import line.

3. **Import Requirements**:
   - For ID columns, use String type with UUID strings for SQLite compatibility
   - For relationships, import relationship from sqlalchemy.orm- For timestamp default values, import datetime from datetime module
   - Import any enum classes if you use Enum types
   - Import datetime if you use datetime objects
   - Import uuid for UUID generation   - **CRITICAL:** If you use any SQLAlchemy type (e.g., Boolean, Integer, DateTime, ForeignKey, Float, etc.), you MUST import it in the import line: `from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, ...` as needed.
   - **CRITICAL:** For timestamp columns, ALWAYS use `Column(DateTime, default=datetime.utcnow)` NOT `Column(func.now())`

4. **Reserved Names**:
   - **CRITICAL:** Do NOT use reserved SQLAlchemy attribute names like 'metadata', 'registry', 'query', 'query_class' for your column or relationship names. Choose alternative names if the entity description suggests these.

# --- ILLUSTRATIVE EXAMPLE ---
The following code example demonstrates the expected structure and principles for a User model.
Adapt these principles to the specific requirements of the current entity ({entity_name}). Do NOT simply copy the example code.

# CODE EXAMPLE
```python
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Float, Text, JSON, Date, Time, Enum, LargeBinary
from sqlalchemy.orm import relationship
from core.database import Base
import uuid
import enum
from datetime import datetime

class UserRole(enum.Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"

class User(Base):
    __tablename__ = "users"

    # Primary key using String (SQLite-compatible UUID)
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Basic fields
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)    # Enum example
    role = Column(Enum(UserRole), nullable=False, default=UserRole.USER)

    # JSON data - use standard JSON for SQLite compatibility
    preferences = Column(JSON, nullable=True)# Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship example
    posts = relationship("Post", back_populates="author")
    profile = relationship("UserProfile", back_populates="user", uselist=False)
```
# FOREIGN KEY RELATIONSHIP RULES:
1. **Conservative Foreign Key Usage**:
   - Only create foreign key relationships if you're certain the referenced table exists
   - Use descriptive comments for foreign key relationships
   - Prefer nullable foreign keys to avoid constraint violations

2. **Foreign Key Best Practices**:
   - Use this format: `Column(Integer, ForeignKey('table_name.id'), nullable=True)`
   - Always include nullable=True for foreign keys unless absolutely required
   - Add comments explaining the relationship

3. **Referenced Table Naming**:
   - Use lowercase, plural table names (e.g., 'users', 'categories', 'publishers')
   - Ensure referenced column exists (usually 'id')

   EXAMPLE OF SAFE FOREIGN KEY:
```python
class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)

    # Foreign key to publishers table (nullable to avoid constraint errors)
    publisher_id = Column(Integer, ForeignKey('publishers.id'), nullable=True, comment="Reference to publisher")

    # Relationship (optional, can be added later)
    # publisher = relationship("Publisher", back_populates="books")
```


IMPORTANT:
1. Return ONLY the SQLAlchemy model code for {entity_name}.
2. Do not include any explanations, comments, or text after the code.
3. The response should contain ONLY the code itself.
4. ALWAYS include imports for ANY types, classes, or modules used in the model.
5. For ID columns, use String type with UUID string as default: `Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))`.
6. If using Enum types, define the enum class and import enum module but if its best to avoid enum please do.
7. Always import the necesaccy dependencies if being used in the code
8. Use correct indentation when writing to avoid tests failing
IMPORTANT :
- Make foreign keys nullable=True to prevent constraint violations
- Add descriptive comments for all foreign key relationships
- Use standard naming conventions for referenced tables
- Consider whether the referenced table actually exists in the project
"""
# Step 3: Generate the Pydantic schemas
SCHEMA_GENERATION_TEMPLATE = """
You are an expert Pydantic developer helping to create schemas for a FastAPI application.
Generate Pydantic schemas for the following entity:
Entity Name: {entity_name}
# Model Fields placeholder removed entirely

CONTEXT PROVIDED:
Endpoint Code (Defines expected schema names):
```python
{endpoint_code}
```
Model Code (Defines fields/types):
```python
{model_code}
```

# TASK: CREATE PYDANTIC SCHEMAS ONLY
# 1. Analyze the provided `{endpoint_code}` to identify the specific Pydantic schema class names it imports or uses (e.g., `ProductSchema`, `ProductCreate`). You **MUST** generate Python code defining *exactly* these schema classes.
# 2. Use the provided `{model_code}` as the primary reference for determining the fields and their types within the required schemas. Ensure the schema fields align with the model attributes.
# 3. Create Base, Create, and Response schemas as appropriate based on the names found in the endpoint code.

# SCHEMA REQUIREMENTS
1. **Schema Types**:
   - Create Base, Create, and Response schemas as identified from the endpoint code.
2. **Field Types**:
   - Use appropriate Pydantic field types based on the Model Code.
   - Add validation with Field() if needed.
   - Include example values in Config if helpful.
3. **Configuration**:
   - Use `Config: orm_mode = True` for Response schemas that map directly from the model.

# --- ILLUSTRATIVE EXAMPLE ONLY ---
The following code example demonstrates the expected structure and principles for User schemas.
Adapt these principles to the specific requirements of the current entity ({entity_name}) and the schemas identified in the endpoint code. Do NOT simply copy the example code.

# CODE EXAMPLE (Illustrative - Adapt based on context)
```python
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime
from uuid import UUID
# Schema for creating a new User
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="User's username")
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="User's password")
    class Config:
        schema_extra = {{
            "example": {{
                "username": "johndoe",
                "email": "john@example.com",
                "password": "securepassword123"
            }}
        }}
# Schema for User responses
class UserSchema(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    is_active: bool
    created_at: datetime
    updated_at: datetime
    class Config:
        orm_mode = True
```
IMPORTANT:
1.Return ONLY the Pydantic schema code for {entity_name}.
2. Do not include any explanations, comments, or text after the code.
3. The response should contain ONLY the code itself.
4. Always import the necesaccy dependencies if being used in the code
5. Use correct indentation when writing to avoid tests failing
"""
# Step 4: Generate the Alembic migration
MIGRATION_GENERATION_TEMPLATE = """
You are an expert Alembic developer helping to create a database migration for SQLite.
Generate an Alembic migration for the following entity:
Entity Name: {entity_name}
Latest Migration ID: {latest_migration_id}

CONTEXT PROVIDED:
Model Code:
```python
{model_code}
```

# TASK: CREATE SQLITE-COMPATIBLE ALEMBIC MIGRATION
# Analyze the provided SQLAlchemy `{model_code}` to determine the required table name, columns, types, constraints, and indexes.
# Generate an Alembic migration script using `op` commands to create this table.
# REQUIRED REVISION INFORMATION
    -The migration MUST have down_revision set EXACTLY as follows:
    down_revision = '{latest_migration_id}'
    Do not use empty strings, None, or any other value for down_revision.
# SQLITE COMPATIBILITY REQUIREMENTS
1. **SQLite Limitations**:
   - DO NOT use ALTER TABLE operations (not fully supported in SQLite)
   - DO NOT use UUID types directly (use String type instead)
   - DO NOT use server_default with complex functions (use simple text constants)
   - Avoid column type modifications after creation

2. **Structure**:
   - Include revision ID and comments
   - Implement both upgrade() and downgrade() functions
   - Use only SQLite-compatible Alembic op commands

3. **Column Creation**:
   - Define all columns with SQLite-compatible types
   - Use sa.String() instead of UUIDs or specialized types
   - For dates/times, use either sa.DateTime() or sa.Date()
   - Set server_default to sa.text('CURRENT_TIMESTAMP') for timestamp fields

4. **Dependency Chain**:
   - Set down_revision to '{latest_migration_id}' to ensure this migration runs after the most recent migration
   - Generate a unique revision ID different from '{latest_migration_id}'

# SQLITE-COMPATIBLE EXAMPLE
```python
\"\"\"create table for {entity_name}
Revision ID: a1b2c3d4e5f6
Revises: {latest_migration_id}
Create Date: 2024-03-26 12:00:00.000000
\"\"\"
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func

# revision identifiers
revision = 'a1b2c3d4e5f6'
down_revision = '{latest_migration_id}'  # This ensures it runs after the most recent migration
branch_labels = None
depends_on = None

def upgrade():
    # Create table with SQLite compatibility
    op.create_table(
        '{entity_name}s',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_{entity_name}s_email'), '{entity_name}s', ['email'], unique=False)

def downgrade():
    # Drop table
    op.drop_index(op.f('ix_{entity_name}s_email'), table_name='{entity_name}s')
    op.drop_table('{entity_name}s')
```

IMPORTANT:
1. Return ONLY the Alembic migration code for creating the table for {entity_name}.
2. EXTRACT the table name from the provided model_code by looking for `__tablename__` attribute.
3. If no __tablename__ is found in the model, use the lowercase plural form of {entity_name} as the default table name.
4. Use ONLY SQLite-compatible operations (CREATE TABLE, DROP TABLE, CREATE INDEX, DROP INDEX).
5. AVOID all ALTER TABLE operations which are problematic in SQLite.
6. Use sa.String() instead of UUID or other specialized types.
7. The migration MUST have down_revision set to '{latest_migration_id}' to chain correctly with existing migrations.
8. The revision ID must be a new unique string different from existing IDs.
9. Do not include any explanations, comments, or text after the code.
10. The response should contain ONLY the code itself.
11. The migration MUST have down_revision set to '{latest_migration_id}' to chain correctly with existing migrations.
"""

# Helper Functions Generation Template

HELPER_FUNCTIONS_TEMPLATE = """
You are an expert Python developer helping to create helper functions for a FastAPI application.
Generate helper functions for the following entity:

Entity Name: {entity_name}
Entity Description: {entity_description}
# Entity Fields placeholder removed entirely

CONTEXT PROVIDED:
Endpoint Code (Defines expected helper function names/calls):
```python
{endpoint_code}
```
Model Code (For DB logic):
```python
{model_code}
```
Schema Code (For data structuring):
```python
{schema_code}
```

# TASK: CREATE HELPER FUNCTIONS ONLY
# 1. Analyze the provided `{endpoint_code}` to identify the specific helper function names it imports or calls (e.g., `get_all_products`, `create_product`). You **MUST** generate Python code defining *exactly* these helper functions with the signatures implied by the endpoint calls.
# 2. Determine Implementation Strategy based on Context:
#    - IF `{model_code}` contains actual SQLAlchemy model code (not just a comment like '# Model code not provided'):
#        - Implement the logic within these functions using the provided `{model_code}` for database interactions (via SQLAlchemy Session, assuming `db: Session` is passed if needed based on endpoint usage) and the `{schema_code}` for data validation or structuring inputs/outputs.
#    - ELSE (if `{model_code}` indicates no model was provided/needed):
#        - Implement helper functions that DO NOT require database access or specific model/schema interactions. Focus on utility functions, data transformations, or logic based solely on the endpoint's parameters and description. DO NOT import `Session`, `get_db`, models, or schemas.

# HELPER FUNCTION REQUIREMENTS
1. **Function Types**:
   - Create functions that assist with common operations on this entity (DB-dependent or not, based on context).
   - Include functions that handle specific business logic
   - Create any utility functions needed for this entity

2. **Implementation Requirements**:
   - Use clear docstrings
   - Include proper type hints
   - Add proper error handling
   - Follow Python best practices

# --- ILLUSTRATIVE EXAMPLE ONLY ---
The following code example demonstrates the expected structure and principles for helper functions (using User as an example).
Adapt these principles to generate the specific helper functions required by the provided `{endpoint_code}`, using the context from `{model_code}` and `{schema_code}` for implementation. Do NOT simply copy the example code.

# CODE EXAMPLE
```python
from typing import List, Dict, Optional, Union, Any
from datetime import datetime
import re
from sqlalchemy.orm import Session
from models.user import User
from schemas.user import UserCreate, UserUpdate

def validate_email(email: str) -> bool:
    \"\"\"
    Validate an email address format.

    Args:
        email: The email address to validate

    Returns:
        bool: True if email format is valid, False otherwise
    \"\"\"
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$'
    return bool(re.match(pattern, email))

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    \"\"\"
    Get a user by their email address.

    Args:
        db: Database session
        email: Email to search for

    Returns:
        User object if found, None otherwise
    \"\"\"
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, user_data: UserCreate) -> Union[User, Dict[str, str]]:
    \"\"\"
    Create a new user with validation and error handling.

    Args:
        db: Database session
        user_data: User data for creation

    Returns:
        User object if created successfully, error dict otherwise
    \"\"\"
    # Check if email is valid
    if not validate_email(user_data.email):
        return {{"error": "Invalid email format"}}

    # Check if user already exists
    existing_user = get_user_by_email(db, user_data.email)
    if existing_user:
        return {{"error": "Email already registered"}}

    # Create the user
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        password=user_data.password  # In a real app, hash this password
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user
```

IMPORTANT:
1. Return ONLY the Python code for helper functions related to {entity_name}.
2. Do not include any explanations, comments, or text after the code.
3. The code should be well-organized with proper docstrings and type hints.
4. Include at least 3-5 useful helper functions that would be valuable for this entity.
5. The response should contain ONLY the code itself.
6. Always import the necesaccy dependencies if being used in the code
7. Use correct indentation when writing to avoid tests failing
"""
PYTHON_MODEL_CHANGES_TEMPLATE = """
You are an expert SQLAlchemy developer helping to MODIFY an EXISTING database model.

TASK: ANALYZE REQUIRED CHANGES TO AN EXISTING MODEL
You must identify required changes to an existing SQLAlchemy model based on the user's request.

Entity Name: {entity_name}
User Request: {prompt_description}

EXISTING MODEL:
```{language}
{existing_model_code}
```

{endpoint_context}

INSTRUCTIONS:
1. Carefully examine the existing model above. This model ALREADY EXISTS in the database.
2. Analyze the user's request to identify what changes are needed.
3. Consider all types of changes: adding new fields, modifying existing fields, removing fields, or renaming fields.

RESPONSE FORMAT:
Return a JSON array of change operations, where each operation has these fields:
- "type": The type of change ("add", "modify", "remove", or "rename")
- "field_name": The name of the field to change
- "definition": For "add" and "modify", the SQLAlchemy Column definition
- "new_name": For "rename" operations only, the new field name

Example:
[
  {"type": "add", "field_name": "status", "definition": "Column(Enum(OrderStatus), nullable=False, default=OrderStatus.PROCESSING)"},
  {"type": "modify", "field_name": "price", "definition": "Column(Float, nullable=False)"},
  {"type": "remove", "field_name": "temporary_field"},
  {"type": "rename", "field_name": "customer_name", "new_name": "full_name"}
]

If no changes are needed, return an empty array: []

IMPORTANT:
1. Consider the existing model structure carefully.
2. Only suggest changes specifically requested or implied by the user.
3. For renames, include both the old field name and new field name.
4. For modifications, include the complete new Column definition.
5. If adding an Enum type, use the existing Enum if one exists in the model, otherwise specify it properly in the Column definition.
6. Do NOT suggest any changes to standard fields like id, created_at, updated_at.
7. Use correct indentation when writing to avoid tests failing
"""
