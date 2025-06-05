"""
Enhanced Prompt Template Service with Error Prevention.

This service integrates error patterns into LLM prompts to prevent
common mistakes during code generation.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from app.api.v1.utils.error_pattern_database import (
    ErrorCategory,
    error_pattern_db,
)

logger = logging.getLogger(__name__)


class ComponentType(Enum):
    """Types of components that can be generated."""

    ENDPOINT = "endpoint"
    MODEL = "model"
    SCHEMA = "schema"
    HELPERS = "helpers"
    MIGRATION = "migration"


@dataclass
class PromptContext:
    """Context information for prompt generation."""

    language: str
    component_type: ComponentType
    entity_name: str
    entity_description: str
    project_context: Optional[Dict[str, Any]] = None
    existing_code: Optional[str] = None
    dependencies: Optional[List[str]] = None
    framework_version: Optional[str] = None


class EnhancedPromptService:
    """Service for generating enhanced prompts with error prevention."""

    def __init__(self):
        self.error_db = error_pattern_db

    def generate_enhanced_prompt(self, context: PromptContext, base_prompt: str) -> str:
        """
        Generate an enhanced prompt with error prevention guidelines.

        Args:
            context: Context information for the prompt
            base_prompt: The base prompt template

        Returns:
            Enhanced prompt with error prevention guidelines
        """
        # Start with base prompt
        enhanced_parts = [base_prompt]

        # Add language-specific error prevention
        prevention_guidelines = self._get_prevention_guidelines(context)
        if prevention_guidelines:
            enhanced_parts.append(prevention_guidelines)

        # Add component-specific guidelines
        component_guidelines = self._get_component_guidelines(context)
        if component_guidelines:
            enhanced_parts.append(component_guidelines)

        # Add project context if available
        project_context = self._get_project_context(context)
        if project_context:
            enhanced_parts.append(project_context)

        # Add quality requirements
        quality_requirements = self._get_quality_requirements(context)
        enhanced_parts.append(quality_requirements)

        # Add examples and best practices
        examples = self._get_best_practice_examples(context)
        if examples:
            enhanced_parts.append(examples)

        return "\n\n".join(enhanced_parts)

    def _get_prevention_guidelines(self, context: PromptContext) -> str:
        """Get error prevention guidelines for the language."""
        critical_patterns = self.error_db.get_critical_patterns(context.language)

        if not critical_patterns:
            return ""

        guidelines = [
            f"\n🚨 CRITICAL ERROR PREVENTION for {context.language.upper()}:",
            "Please follow these guidelines to prevent common errors:\n",
        ]

        for pattern in critical_patterns:
            guidelines.append(f"• {pattern.description}:")
            guidelines.append(f"  {pattern.prevention_prompt}")
            guidelines.append("")

        return "\n".join(guidelines)

    def _get_component_guidelines(self, context: PromptContext) -> str:
        """Get component-specific guidelines."""
        component_guides = {
            ComponentType.ENDPOINT: self._get_endpoint_guidelines,
            ComponentType.MODEL: self._get_model_guidelines,
            ComponentType.SCHEMA: self._get_schema_guidelines,
            ComponentType.HELPERS: self._get_helpers_guidelines,
            ComponentType.MIGRATION: self._get_migration_guidelines,
        }

        guide_func = component_guides.get(context.component_type)
        if guide_func:
            return guide_func(context)

        return ""

    def _get_endpoint_guidelines(self, context: PromptContext) -> str:
        """Get endpoint-specific guidelines."""
        if context.language == "python":
            return """
📋 FASTAPI ENDPOINT BEST PRACTICES:
• Always include proper type annotations for parameters and return types
• Use dependency injection for database sessions: `db: Session = Depends(get_db)`
• Wrap database operations in try-except blocks with proper rollback
• Use Pydantic models for request/response validation
• Include proper HTTP status codes and error responses
• Add proper logging for debugging and monitoring

Example structure:
```python
@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
) -> UserResponse:
    try:
        # Implementation with error handling
        db_user = User(**user_data.dict())
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
```"""

        elif context.language == "javascript":
            return """
📋 EXPRESS.JS ENDPOINT BEST PRACTICES:
• Always wrap async operations in try-catch blocks
• Use proper error middleware for error handling
• Validate input data using express-validator or Joi
• Use consistent response format: { success: boolean, data?: any, error?: string }
• Include proper HTTP status codes
• Use middleware for authentication and validation

Example structure:
```javascript
router.post('/users', [
    body('email').isEmail(),
    body('name').notEmpty()
], async (req, res, next) => {
    try {
        const errors = validationResult(req);
        if (!errors.isEmpty()) {
            return res.status(400).json({
                success: false,
                error: 'Validation failed',
                details: errors.array()
            });
        }

        const user = await User.create(req.body);
        res.status(201).json({ success: true, data: user });
    } catch (error) {
        next(error);
    }
});
```"""

        return ""

    def _get_model_guidelines(self, context: PromptContext) -> str:
        """Get model-specific guidelines."""
        if context.language == "python":
            return """
📋 SQLALCHEMY MODEL BEST PRACTICES:
• Use proper column types and constraints
• Include __tablename__ for explicit table naming
• Add proper indexes for frequently queried fields
• Use relationships with proper back_populates
• Include timestamps (created_at, updated_at) when appropriate
• Add proper validation constraints
• Use UUIDs for primary keys when appropriate

Example structure:
```python
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    posts = relationship("Post", back_populates="author")
```"""

        elif context.language == "javascript":
            return """
📋 JAVASCRIPT MODEL BEST PRACTICES:
• Use proper schema validation (Mongoose, Sequelize, etc.)
• Include proper data types and validation rules
• Add indexes for frequently queried fields
• Use proper naming conventions (camelCase for fields)
• Include timestamps when appropriate
• Add proper relationships and foreign keys

Example structure (Mongoose):
```javascript
const userSchema = new mongoose.Schema({
    email: {
        type: String,
        required: true,
        unique: true,
        lowercase: true,
        trim: true
    },
    name: {
        type: String,
        required: true,
        trim: true
    }
}, {
    timestamps: true,
    toJSON: { virtuals: true },
    toObject: { virtuals: true }
});

userSchema.index({ email: 1 });
module.exports = mongoose.model('User', userSchema);
```"""

        return ""

    def _get_schema_guidelines(self, context: PromptContext) -> str:
        """Get schema-specific guidelines."""
        if context.language == "python":
            return """
📋 PYDANTIC SCHEMA BEST PRACTICES:
• Use Pydantic v2 syntax with `from_attributes = True`
• Create separate schemas for Create, Update, and Response operations
• Use proper field validation and constraints
• Include example values for API documentation
• Use Union types for optional fields appropriately
• Inherit from BaseModel consistently

Example structure:
```python
class UserBase(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=100)

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = Field(None, min_length=1, max_length=100)

class UserResponse(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
```"""

        elif context.language == "javascript":
            return """
📋 JAVASCRIPT VALIDATION SCHEMA BEST PRACTICES:
• Use consistent validation library (Joi, express-validator, etc.)
• Validate all input fields with appropriate constraints
• Provide clear error messages
• Use proper data type validation
• Include sanitization where needed

Example structure (Joi):
```javascript
const userCreateSchema = Joi.object({
    email: Joi.string().email().required(),
    name: Joi.string().min(1).max(100).required(),
    password: Joi.string().min(8).required()
});

const userUpdateSchema = Joi.object({
    email: Joi.string().email().optional(),
    name: Joi.string().min(1).max(100).optional()
});

module.exports = {
    userCreateSchema,
    userUpdateSchema
};
```"""

        return ""

    def _get_helpers_guidelines(self, context: PromptContext) -> str:
        """Get helpers-specific guidelines."""
        return """
📋 HELPER FUNCTIONS BEST PRACTICES:
• Create pure functions when possible (no side effects)
• Use proper error handling and return meaningful errors
• Include proper type annotations/JSDoc
• Make functions testable and modular
• Use consistent naming conventions
• Add proper logging for debugging
• Handle edge cases and null/undefined values
"""

    def _get_migration_guidelines(self, context: PromptContext) -> str:
        """Get migration-specific guidelines."""
        return """
📋 DATABASE MIGRATION BEST PRACTICES:
• Always include both upgrade and downgrade operations
• Use proper naming conventions with timestamps
• Test migrations on sample data before production
• Include proper indexes in migrations
• Handle foreign key constraints properly
• Add proper data validation in migrations
"""

    def _get_project_context(self, context: PromptContext) -> Optional[str]:
        """Get project-specific context if available."""
        if not context.project_context:
            return None

        context_parts = ["📁 PROJECT CONTEXT:"]

        if context.existing_code:
            context_parts.append("• Existing code patterns detected")

        if context.dependencies:
            context_parts.append(f"• Dependencies: {', '.join(context.dependencies)}")

        if context.framework_version:
            context_parts.append(f"• Framework version: {context.framework_version}")

        return "\n".join(context_parts)

    def _get_quality_requirements(self, context: PromptContext) -> str:
        """Get quality requirements for the generated code."""
        return """
✅ CODE QUALITY REQUIREMENTS:
• Write clean, readable, and maintainable code
• Follow language-specific style guides (PEP 8 for Python, StandardJS for JavaScript)
• Include proper error handling and edge case management
• Use meaningful variable and function names
• Add appropriate comments for complex logic
• Ensure code is testable and follows SOLID principles
• Optimize for performance and security
• Follow the project's existing patterns and conventions
"""

    def _get_best_practice_examples(self, context: PromptContext) -> Optional[str]:
        """Get best practice examples relevant to the context."""
        # Get examples from error patterns
        relevant_patterns = self.error_db.get_patterns_by_category(
            ErrorCategory.LOGIC, context.language
        )

        if not relevant_patterns:
            return None

        examples = ["💡 EXAMPLES OF BEST PRACTICES:"]

        for pattern in relevant_patterns[:2]:  # Limit to 2 examples
            if pattern.example_fix:
                examples.append(f"\n{pattern.description}:")
                examples.append(pattern.example_fix)

        return "\n".join(examples) if len(examples) > 1 else None


# Global instance
enhanced_prompt_service = EnhancedPromptService()
