"""
Comprehensive Error Pattern Database

This module maintains a comprehensive database of error patterns, their solutions,
and historical tracking for the quality assurance pipeline.
"""

import json
import logging
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ErrorCategory(Enum):
    """Error categories"""

    SYNTAX = "syntax"
    SEMANTIC = "semantic"
    RUNTIME = "runtime"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    ARCHITECTURAL = "architectural"
    INTEGRATION = "integration"


@dataclass
class ErrorPattern:
    """Represents an error pattern with metadata"""

    id: str
    name: str
    category: ErrorCategory
    severity: ErrorSeverity
    pattern: str
    description: str
    language: str
    solution: str
    auto_fixable: bool
    fix_confidence: float  # 0.0 to 1.0
    occurrence_count: int = 0
    last_seen: Optional[str] = None
    fix_success_rate: float = 0.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ErrorPatternDatabase:
    """Comprehensive error pattern database with historical tracking"""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize the error pattern database"""
        if db_path is None:
            db_path = Path(__file__).parent / "data" / "error_patterns.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_database()
        self._populate_default_patterns()

    def _init_database(self):
        """Initialize the SQLite database schema"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create error patterns table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS error_patterns (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    description TEXT NOT NULL,
                    language TEXT NOT NULL,
                    solution TEXT NOT NULL,
                    auto_fixable BOOLEAN NOT NULL,
                    fix_confidence REAL NOT NULL,
                    occurrence_count INTEGER DEFAULT 0,
                    last_seen TEXT,
                    fix_success_rate REAL DEFAULT 0.0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """
            )

            # Create error occurrences table for historical tracking
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS error_occurrences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_id TEXT NOT NULL,
                    project_id TEXT,
                    file_path TEXT,
                    line_number INTEGER,
                    error_context TEXT,
                    fix_applied BOOLEAN DEFAULT FALSE,
                    fix_successful BOOLEAN DEFAULT FALSE,
                    fix_time_ms INTEGER,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (pattern_id) REFERENCES error_patterns (id)
                )
            """
            )

            # Create indexes for performance
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_pattern_language ON error_patterns (language)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_pattern_category ON error_patterns (category)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_occurrence_pattern ON error_occurrences (pattern_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_occurrence_timestamp ON error_occurrences (timestamp)"
            )

            conn.commit()

    def _populate_default_patterns(self):
        """Populate database with default error patterns"""
        default_patterns = self._get_default_patterns()

        for pattern in default_patterns:
            if not self.get_pattern(pattern.id):
                self.add_pattern(pattern)

    def _get_default_patterns(self) -> List[ErrorPattern]:
        """Get comprehensive default error patterns"""
        now = datetime.now(timezone.utc).isoformat()

        patterns = []

        # Python Error Patterns
        python_patterns = [
            ErrorPattern(
                id="py_undefined_variable",
                name="Undefined Variable",
                category=ErrorCategory.SYNTAX,
                severity=ErrorSeverity.HIGH,
                pattern=r"NameError: name '(\w+)' is not defined",
                description="Variable used before definition",
                language="python",
                solution="Define the variable before use or import the required module",
                auto_fixable=True,
                fix_confidence=0.8,
                created_at=now,
                updated_at=now,
            ),
            ErrorPattern(
                id="py_import_error",
                name="Import Error",
                category=ErrorCategory.SEMANTIC,
                severity=ErrorSeverity.HIGH,
                pattern=r"ImportError: No module named '(\w+)'",
                description="Missing module import",
                language="python",
                solution="Install the required module using pip or add to requirements.txt",
                auto_fixable=True,
                fix_confidence=0.9,
                created_at=now,
                updated_at=now,
            ),
            ErrorPattern(
                id="py_indentation_error",
                name="Indentation Error",
                category=ErrorCategory.SYNTAX,
                severity=ErrorSeverity.MEDIUM,
                pattern=r"IndentationError: expected an indented block",
                description="Incorrect indentation",
                language="python",
                solution="Fix indentation to match Python standards (4 spaces)",
                auto_fixable=True,
                fix_confidence=0.95,
                created_at=now,
                updated_at=now,
            ),
            ErrorPattern(
                id="py_sql_injection",
                name="SQL Injection Vulnerability",
                category=ErrorCategory.SECURITY,
                severity=ErrorSeverity.CRITICAL,
                pattern=r"execute\([\"'].*%s.*[\"']\)",
                description="Potential SQL injection vulnerability",
                language="python",
                solution="Use parameterized queries or ORM methods",
                auto_fixable=True,
                fix_confidence=0.7,
                created_at=now,
                updated_at=now,
            ),
            ErrorPattern(
                id="py_unused_import",
                name="Unused Import",
                category=ErrorCategory.STYLE,
                severity=ErrorSeverity.LOW,
                pattern=r"imported but unused",
                description="Imported module not used in code",
                language="python",
                solution="Remove unused import or add to __all__",
                auto_fixable=True,
                fix_confidence=0.9,
                created_at=now,
                updated_at=now,
            ),
        ]

        # JavaScript Error Patterns
        js_patterns = [
            ErrorPattern(
                id="js_undefined_variable",
                name="Undefined Variable",
                category=ErrorCategory.RUNTIME,
                severity=ErrorSeverity.HIGH,
                pattern=r"ReferenceError: (\w+) is not defined",
                description="Variable used before declaration",
                language="javascript",
                solution="Declare the variable using let, const, or var",
                auto_fixable=True,
                fix_confidence=0.8,
                created_at=now,
                updated_at=now,
            ),
            ErrorPattern(
                id="js_syntax_error",
                name="Syntax Error",
                category=ErrorCategory.SYNTAX,
                severity=ErrorSeverity.HIGH,
                pattern=r"SyntaxError: Unexpected token",
                description="Invalid JavaScript syntax",
                language="javascript",
                solution="Fix syntax error according to JavaScript grammar",
                auto_fixable=True,
                fix_confidence=0.7,
                created_at=now,
                updated_at=now,
            ),
            ErrorPattern(
                id="js_missing_semicolon",
                name="Missing Semicolon",
                category=ErrorCategory.STYLE,
                severity=ErrorSeverity.LOW,
                pattern=r"Missing semicolon",
                description="Semicolon missing at end of statement",
                language="javascript",
                solution="Add semicolon at the end of statement",
                auto_fixable=True,
                fix_confidence=0.95,
                created_at=now,
                updated_at=now,
            ),
            ErrorPattern(
                id="js_promise_not_handled",
                name="Unhandled Promise",
                category=ErrorCategory.RUNTIME,
                severity=ErrorSeverity.MEDIUM,
                pattern=r"UnhandledPromiseRejectionWarning",
                description="Promise rejection not handled",
                language="javascript",
                solution="Add .catch() handler or use try-catch with async/await",
                auto_fixable=True,
                fix_confidence=0.8,
                created_at=now,
                updated_at=now,
            ),
        ]

        # TypeScript Error Patterns
        ts_patterns = [
            ErrorPattern(
                id="ts_type_error",
                name="Type Error",
                category=ErrorCategory.SEMANTIC,
                severity=ErrorSeverity.HIGH,
                pattern=r"Type '(\w+)' is not assignable to type '(\w+)'",
                description="Type mismatch",
                language="typescript",
                solution="Fix type annotation or cast to correct type",
                auto_fixable=True,
                fix_confidence=0.7,
                created_at=now,
                updated_at=now,
            ),
            ErrorPattern(
                id="ts_property_not_exist",
                name="Property Does Not Exist",
                category=ErrorCategory.SEMANTIC,
                severity=ErrorSeverity.HIGH,
                pattern=r"Property '(\w+)' does not exist on type '(\w+)'",
                description="Accessing non-existent property",
                language="typescript",
                solution="Add property to interface or use optional chaining",
                auto_fixable=True,
                fix_confidence=0.6,
                created_at=now,
                updated_at=now,
            ),
        ]

        # General Architectural Patterns
        arch_patterns = [
            ErrorPattern(
                id="arch_circular_dependency",
                name="Circular Dependency",
                category=ErrorCategory.ARCHITECTURAL,
                severity=ErrorSeverity.HIGH,
                pattern=r"Circular dependency detected",
                description="Modules depend on each other cyclically",
                language="general",
                solution="Refactor to break circular dependency using dependency injection",
                auto_fixable=False,
                fix_confidence=0.3,
                created_at=now,
                updated_at=now,
            ),
            ErrorPattern(
                id="arch_tight_coupling",
                name="Tight Coupling",
                category=ErrorCategory.ARCHITECTURAL,
                severity=ErrorSeverity.MEDIUM,
                pattern=r"High coupling detected",
                description="Components are too tightly coupled",
                language="general",
                solution="Introduce interfaces and dependency injection",
                auto_fixable=False,
                fix_confidence=0.2,
                created_at=now,
                updated_at=now,
            ),
        ]

        patterns.extend(python_patterns)
        patterns.extend(js_patterns)
        patterns.extend(ts_patterns)
        patterns.extend(arch_patterns)

        return patterns

    def add_pattern(self, pattern: ErrorPattern) -> bool:
        """Add a new error pattern to the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO error_patterns
                    (id, name, category, severity, pattern, description, language,
                     solution, auto_fixable, fix_confidence, occurrence_count,
                     last_seen, fix_success_rate, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        pattern.id,
                        pattern.name,
                        pattern.category.value,
                        pattern.severity.value,
                        pattern.pattern,
                        pattern.description,
                        pattern.language,
                        pattern.solution,
                        pattern.auto_fixable,
                        pattern.fix_confidence,
                        pattern.occurrence_count,
                        pattern.last_seen,
                        pattern.fix_success_rate,
                        pattern.created_at,
                        pattern.updated_at or datetime.now(timezone.utc).isoformat(),
                    ),
                )

                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding pattern {pattern.id}: {e}")
            return False

    def get_pattern(self, pattern_id: str) -> Optional[ErrorPattern]:
        """Get an error pattern by ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM error_patterns WHERE id = ?", (pattern_id,)
                )
                row = cursor.fetchone()

                if row:
                    return ErrorPattern(
                        id=row[0],
                        name=row[1],
                        category=ErrorCategory(row[2]),
                        severity=ErrorSeverity(row[3]),
                        pattern=row[4],
                        description=row[5],
                        language=row[6],
                        solution=row[7],
                        auto_fixable=row[8],
                        fix_confidence=row[9],
                        occurrence_count=row[10],
                        last_seen=row[11],
                        fix_success_rate=row[12],
                        created_at=row[13],
                        updated_at=row[14],
                    )
                return None
        except Exception as e:
            logger.error(f"Error getting pattern {pattern_id}: {e}")
            return None

    def get_patterns_by_language(self, language: str) -> List[ErrorPattern]:
        """Get all error patterns for a specific language"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM error_patterns WHERE language = ? OR language = 'general'",
                    (language,),
                )
                rows = cursor.fetchall()

                patterns = []
                for row in rows:
                    patterns.append(
                        ErrorPattern(
                            id=row[0],
                            name=row[1],
                            category=ErrorCategory(row[2]),
                            severity=ErrorSeverity(row[3]),
                            pattern=row[4],
                            description=row[5],
                            language=row[6],
                            solution=row[7],
                            auto_fixable=row[8],
                            fix_confidence=row[9],
                            occurrence_count=row[10],
                            last_seen=row[11],
                            fix_success_rate=row[12],
                            created_at=row[13],
                            updated_at=row[14],
                        )
                    )

                return patterns
        except Exception as e:
            logger.error(f"Error getting patterns for language {language}: {e}")
            return []

    def record_error_occurrence(
        self,
        pattern_id: str,
        project_id: Optional[str] = None,
        file_path: Optional[str] = None,
        line_number: Optional[int] = None,
        error_context: Optional[str] = None,
    ) -> bool:
        """Record an error occurrence for historical tracking"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Record occurrence
                cursor.execute(
                    """
                    INSERT INTO error_occurrences
                    (pattern_id, project_id, file_path, line_number, error_context, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        pattern_id,
                        project_id,
                        file_path,
                        line_number,
                        error_context,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )

                # Update pattern statistics
                cursor.execute(
                    """
                    UPDATE error_patterns
                    SET occurrence_count = occurrence_count + 1,
                        last_seen = ?,
                        updated_at = ?
                    WHERE id = ?
                """,
                    (
                        datetime.now(timezone.utc).isoformat(),
                        datetime.now(timezone.utc).isoformat(),
                        pattern_id,
                    ),
                )

                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error recording occurrence for pattern {pattern_id}: {e}")
            return False

    def record_fix_attempt(
        self, pattern_id: str, fix_successful: bool, fix_time_ms: Optional[int] = None
    ) -> bool:
        """Record a fix attempt and update success rate"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Update the latest occurrence with fix result
                cursor.execute(
                    """
                    UPDATE error_occurrences
                    SET fix_applied = TRUE, fix_successful = ?, fix_time_ms = ?
                    WHERE pattern_id = ? AND timestamp = (
                        SELECT MAX(timestamp) FROM error_occurrences WHERE pattern_id = ?
                    )
                """,
                    (fix_successful, fix_time_ms, pattern_id, pattern_id),
                )

                # Calculate new success rate
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) as total_fixes,
                        SUM(CASE WHEN fix_successful = 1 THEN 1 ELSE 0 END) as successful_fixes
                    FROM error_occurrences
                    WHERE pattern_id = ? AND fix_applied = 1
                """,
                    (pattern_id,),
                )

                result = cursor.fetchone()
                if result and result[0] > 0:
                    success_rate = result[1] / result[0]

                    cursor.execute(
                        """
                        UPDATE error_patterns
                        SET fix_success_rate = ?, updated_at = ?
                        WHERE id = ?
                    """,
                        (
                            success_rate,
                            datetime.now(timezone.utc).isoformat(),
                            pattern_id,
                        ),
                    )

                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error recording fix attempt for pattern {pattern_id}: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about error patterns"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Total patterns by language
                cursor.execute(
                    """
                    SELECT language, COUNT(*) as count
                    FROM error_patterns
                    GROUP BY language
                """
                )
                patterns_by_language = dict(cursor.fetchall())

                # Total occurrences by category
                cursor.execute(
                    """
                    SELECT ep.category, COUNT(eo.id) as count
                    FROM error_patterns ep
                    LEFT JOIN error_occurrences eo ON ep.id = eo.pattern_id
                    GROUP BY ep.category
                """
                )
                occurrences_by_category = dict(cursor.fetchall())

                # Most common errors
                cursor.execute(
                    """
                    SELECT ep.name, ep.occurrence_count
                    FROM error_patterns ep
                    ORDER BY ep.occurrence_count DESC
                    LIMIT 10
                """
                )
                most_common_errors = cursor.fetchall()

                # Best fix success rates
                cursor.execute(
                    """
                    SELECT ep.name, ep.fix_success_rate
                    FROM error_patterns ep
                    WHERE ep.occurrence_count > 0
                    ORDER BY ep.fix_success_rate DESC
                    LIMIT 10
                """
                )
                best_fix_rates = cursor.fetchall()

                return {
                    "total_patterns": sum(patterns_by_language.values()),
                    "patterns_by_language": patterns_by_language,
                    "occurrences_by_category": occurrences_by_category,
                    "most_common_errors": most_common_errors,
                    "best_fix_rates": best_fix_rates,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}

    def export_patterns(self, file_path: str) -> bool:
        """Export all patterns to JSON file"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM error_patterns")
                rows = cursor.fetchall()

                patterns = []
                for row in rows:
                    pattern = ErrorPattern(
                        id=row[0],
                        name=row[1],
                        category=ErrorCategory(row[2]),
                        severity=ErrorSeverity(row[3]),
                        pattern=row[4],
                        description=row[5],
                        language=row[6],
                        solution=row[7],
                        auto_fixable=row[8],
                        fix_confidence=row[9],
                        occurrence_count=row[10],
                        last_seen=row[11],
                        fix_success_rate=row[12],
                        created_at=row[13],
                        updated_at=row[14],
                    )
                    # Convert to dict and handle enums
                    pattern_dict = asdict(pattern)
                    pattern_dict["category"] = pattern.category.value
                    pattern_dict["severity"] = pattern.severity.value
                    patterns.append(pattern_dict)

                with open(file_path, "w") as f:
                    json.dump(patterns, f, indent=2)

                return True
        except Exception as e:
            logger.error(f"Error exporting patterns: {e}")
            return False


# Global instance
error_db = ErrorPatternDatabase()


def get_error_database() -> ErrorPatternDatabase:
    """Get the global error pattern database instance"""
    return error_db
