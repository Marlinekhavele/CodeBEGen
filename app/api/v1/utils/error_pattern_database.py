"""
Error Pattern Database for LLM Prompt Enhancement.

This module contains common error patterns found in generated code
and provides prevention strategies for prompt engineering.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List


class ErrorCategory(Enum):
    """Categories of common errors in generated code."""

    SYNTAX = "syntax"
    IMPORT = "import"
    TYPE = "type"
    LOGIC = "logic"
    CONFIGURATION = "configuration"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"


class Severity(Enum):
    """Severity levels for errors."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ErrorPattern:
    """Represents a common error pattern and its prevention strategy."""

    category: ErrorCategory
    severity: Severity
    pattern: str
    description: str
    prevention_prompt: str
    example_fix: str
    language: str = "python"  # or "javascript", "typescript"


class ErrorPatternDatabase:
    """Database of common error patterns and prevention strategies."""

    def __init__(self):
        self.patterns: List[ErrorPattern] = []
        self._initialize_patterns()

    def _initialize_patterns(self):
        """Initialize the database with common error patterns."""

        # Python-specific patterns
        self.patterns.extend(
            [
                ErrorPattern(
                    category=ErrorCategory.CONFIGURATION,
                    severity=Severity.HIGH,
                    pattern="orm_mode = True",
                    description="Pydantic v1 configuration in v2 environment",
                    prevention_prompt="""
IMPORTANT: Use Pydantic v2 syntax. In Config classes, use:
- `from_attributes = True` instead of `orm_mode = True`
- `arbitrary_types_allowed = True` instead of `allow_arbitrary_types = True`
Example:
```python
class Config:
    from_attributes = True
    arbitrary_types_allowed = True
```""",
                    example_fix="""
# WRONG (Pydantic v1):
class UserSchema(BaseModel):
    class Config:
        orm_mode = True

# CORRECT (Pydantic v2):
class UserSchema(BaseModel):
    class Config:
        from_attributes = True
""",
                    language="python",
                ),
                ErrorPattern(
                    category=ErrorCategory.IMPORT,
                    severity=Severity.MEDIUM,
                    pattern="from typing import Optional",
                    description="Missing typing imports for modern Python",
                    prevention_prompt="""
IMPORTANT: Always include necessary typing imports at the top:
```python
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
```
For Python 3.9+, you can also use built-in generics:
```python
from __future__ import annotations
```""",
                    example_fix="""
# Add at top of file:
from typing import Optional, List, Dict, Any
from datetime import datetime
""",
                    language="python",
                ),
                ErrorPattern(
                    category=ErrorCategory.LOGIC,
                    severity=Severity.HIGH,
                    pattern="db.commit()",
                    description="Missing exception handling for database operations",
                    prevention_prompt="""
IMPORTANT: Always wrap database operations in try-except blocks:
```python
try:
    db.add(instance)
    db.commit()
    db.refresh(instance)
except Exception as e:
    db.rollback()
    raise HTTPException(status_code=500, detail=str(e))
```""",
                    example_fix="""
# WRONG:
db.add(user)
db.commit()

# CORRECT:
try:
    db.add(user)
    db.commit()
    db.refresh(user)
except Exception as e:
    db.rollback()
    raise HTTPException(status_code=500, detail=str(e))
""",
                    language="python",
                ),
                ErrorPattern(
                    category=ErrorCategory.TYPE,
                    severity=Severity.MEDIUM,
                    pattern="def function_name(",
                    description="Missing type annotations",
                    prevention_prompt="""
IMPORTANT: Always include type annotations for functions:
```python
def create_user(user_data: UserCreate, db: Session) -> User:
    # implementation

async def get_users(skip: int = 0, limit: int = 100) -> List[User]:
    # implementation
```""",
                    example_fix="""
# WRONG:
def create_user(user_data, db):
    return user

# CORRECT:
def create_user(user_data: UserCreate, db: Session) -> User:
    return user
""",
                    language="python",
                ),
                ErrorPattern(
                    category=ErrorCategory.SECURITY,
                    severity=Severity.CRITICAL,
                    pattern="eval(",
                    description="Dangerous eval() usage",
                    prevention_prompt="""
CRITICAL: Never use eval() or exec() on user input. Use safe alternatives:
- For JSON: use json.loads()
- For expressions: use ast.literal_eval()
- For validation: use Pydantic models
""",
                    example_fix="""
# WRONG:
result = eval(user_input)

# CORRECT:
import json
result = json.loads(user_input)
""",
                    language="python",
                ),
            ]
        )

        # JavaScript-specific patterns
        self.patterns.extend(
            [
                ErrorPattern(
                    category=ErrorCategory.SYNTAX,
                    severity=Severity.MEDIUM,
                    pattern="require(",
                    description="Mixed import syntax in modern JavaScript",
                    prevention_prompt="""
IMPORTANT: Use consistent import syntax. For modern Node.js:
```javascript
// Use ES6 imports
import express from 'express';
import { body, validationResult } from 'express-validator';

// Or CommonJS consistently
const express = require('express');
const { body, validationResult } = require('express-validator');
```""",
                    example_fix="""
// WRONG (mixed):
import express from 'express';
const router = require('express').Router();

// CORRECT:
import express from 'express';
const router = express.Router();
""",
                    language="javascript",
                ),
                ErrorPattern(
                    category=ErrorCategory.LOGIC,
                    severity=Severity.HIGH,
                    pattern="res.json(",
                    description="Missing error handling in Express routes",
                    prevention_prompt="""
IMPORTANT: Always wrap route handlers with error handling:
```javascript
router.get('/users', async (req, res, next) => {
    try {
        const users = await User.find();
        res.json({ success: true, data: users });
    } catch (error) {
        next(error); // Pass to error middleware
    }
});
```""",
                    example_fix="""
// WRONG:
router.get('/users', async (req, res) => {
    const users = await User.find();
    res.json(users);
});

// CORRECT:
router.get('/users', async (req, res, next) => {
    try {
        const users = await User.find();
        res.json({ success: true, data: users });
    } catch (error) {
        next(error);
    }
});
""",
                    language="javascript",
                ),
                ErrorPattern(
                    category=ErrorCategory.SECURITY,
                    severity=Severity.CRITICAL,
                    pattern="eval(",
                    description="Dangerous eval() usage in JavaScript",
                    prevention_prompt="""
CRITICAL: Never use eval() on user input. Use safe alternatives:
- For JSON: use JSON.parse()
- For validation: use proper validators like Joi
- For dynamic imports: use dynamic import() syntax
""",
                    example_fix="""
// WRONG:
const result = eval(userInput);

// CORRECT:
const result = JSON.parse(userInput);
""",
                    language="javascript",
                ),
            ]
        )

    def get_patterns_by_category(
        self, category: ErrorCategory, language: str = None
    ) -> List[ErrorPattern]:
        """Get all patterns for a specific category."""
        patterns = [p for p in self.patterns if p.category == category]
        if language:
            patterns = [p for p in patterns if p.language == language]
        return patterns

    def get_patterns_by_severity(
        self, severity: Severity, language: str = None
    ) -> List[ErrorPattern]:
        """Get all patterns for a specific severity level."""
        patterns = [p for p in self.patterns if p.severity == severity]
        if language:
            patterns = [p for p in patterns if p.language == language]
        return patterns

    def get_prevention_prompts(self, language: str) -> str:
        """Get all prevention prompts for a language as a formatted string."""
        patterns = [p for p in self.patterns if p.language == language]

        # Group by category
        by_category = {}
        for pattern in patterns:
            category = pattern.category.value
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(pattern)

        # Format as prompt
        prompt_parts = [
            f"\n=== COMMON {language.upper()} ERROR PREVENTION GUIDELINES ===\n"
        ]

        for category, category_patterns in by_category.items():
            prompt_parts.append(f"\n--- {category.upper()} BEST PRACTICES ---")
            for pattern in category_patterns:
                if pattern.severity in [Severity.CRITICAL, Severity.HIGH]:
                    prompt_parts.append(pattern.prevention_prompt)

        return "\n".join(prompt_parts)

    def get_critical_patterns(self, language: str) -> List[ErrorPattern]:
        """Get critical and high severity patterns for a language."""
        return [
            p
            for p in self.patterns
            if p.language == language
            and p.severity in [Severity.CRITICAL, Severity.HIGH]
        ]

    def add_pattern(self, pattern: ErrorPattern):
        """Add a new error pattern to the database."""
        self.patterns.append(pattern)

    def search_patterns(self, keyword: str, language: str = None) -> List[ErrorPattern]:
        """Search patterns by keyword in description or pattern."""
        results = []
        keyword_lower = keyword.lower()

        for pattern in self.patterns:
            if language and pattern.language != language:
                continue

            if (
                keyword_lower in pattern.description.lower()
                or keyword_lower in pattern.pattern.lower()
            ):
                results.append(pattern)

        return results


# Global instance
error_pattern_db = ErrorPatternDatabase()
