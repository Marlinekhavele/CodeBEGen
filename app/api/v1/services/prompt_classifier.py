import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class PromptIntent(Enum):
    """Enumeration of different prompt intents"""

    CREATE_NEW_ENDPOINT = "create_new_endpoint"
    FIX_ERROR = "fix_error"
    UPDATE_EXISTING = "update_existing"
    ADD_FUNCTIONALITY = "add_functionality"
    REFACTOR_CODE = "refactor_code"
    UNCLEAR = "unclear"


@dataclass
class ClassificationResult:
    """Result of prompt classification"""

    intent: PromptIntent
    confidence: float
    reasoning: str
    extracted_info: Dict[str, any]


class PromptClassifier:
    """Service to classify user prompts into different intents"""

    def __init__(self):
        self.error_keywords = [
            # Direct error indicators
            "error",
            "bug",
            "fix",
            "broken",
            "not working",
            "issue",
            "problem",
            "exception",
            "crash",
            "fail",
            "failing",
            "failure",
            "incorrect",
            # Specific error types
            "syntax error",
            "import error",
            "runtime error",
            "logic error",
            "404",
            "500",
            "400",
            "403",
            "401",
            "missing",
            "undefined",
            "null reference",
            "key error",
            "type error",
            "attribute error",
            # Pydantic/Configuration errors
            "from_attributes",
            "orm_mode",
            "config attribute",
            "use from_orm",
            "pydantic",
            "configuration error",
            "schema error",
            "validation error",
            # Error manifestations
            "doesn't work",
            "not responding",
            "throws",
            "raises",
            "gets stuck",
            "infinite loop",
            "memory leak",
            "performance issue",
            "slow",
            "timeout",
            "connection failed",
            "database error",
        ]

        self.creation_keywords = [
            # Direct creation indicators
            "create",
            "build",
            "make",
            "generate",
            "new",
            "add",
            "implement",
            "develop",
            "design",
            "construct",
            "establish",
            "set up",
            # Endpoint-specific creation
            "endpoint",
            "api",
            "route",
            "controller",
            "handler",
            "service",
            "CRUD",
            "REST",
            "GET",
            "POST",
            "PUT",
            "DELETE",
            "PATCH",
            # Feature creation
            "feature",
            "functionality",
            "capability",
            "module",
            "component",
            "system",
            "integration",
            "workflow",
            "process",
        ]

        self.update_keywords = [
            # Modification indicators
            "update",
            "modify",
            "change",
            "edit",
            "alter",
            "improve",
            "enhance",
            "extend",
            "expand",
            "upgrade",
            "refactor",
            # Specific updates
            "add field",
            "remove field",
            "change validation",
            "update schema",
            "modify endpoint",
            "enhance functionality",
            "optimize",
        ]

        self.error_patterns = [
            # Error reporting patterns
            r"getting.*(error|exception)",
            r"returns.*(error|null|undefined)",
            r"throws.*(error|exception)",
            r"status.*(4\d\d|5\d\d)",
            r"(can't|cannot|unable).*(connect|access|find|load)",
            r"(missing|not found|undefined).*(import|module|function|variable)",
            # Error descriptions
            r"when.*try.*(get|post|put|delete).*error",
            r"endpoint.*(not working|failing|broken)",
            r"database.*(connection|query).*fail",
        ]

        self.creation_patterns = [
            # Creation request patterns
            r"(create|build|make|generate).*(endpoint|api|route)",
            r"need.*(new|create).*(endpoint|functionality|feature)",
            r"(implement|add).*(CRUD|REST|API)",
            r"(GET|POST|PUT|DELETE|PATCH).*(endpoint|route).*for",
            r"build.*api.*for.*(manage|handling|creating)",
            # Feature request patterns
            r"want.*(functionality|feature).*to",
            r"system.*should.*(allow|enable|support)",
            r"users.*should.*be able.*to",
        ]

    async def classify_prompt(
        self,
        prompt: str,
        additional_context: Optional[str] = None,
        existing_endpoints: Optional[List[str]] = None,
    ) -> ClassificationResult:
        """
        Classify a prompt to determine the user's intent

        Args:
            prompt: The user's prompt
            additional_context: Any additional context provided
            existing_endpoints: List of existing endpoints in the project

        Returns:
            ClassificationResult: The classification result with intent and confidence
        """
        logger.info(f"Classifying prompt: {prompt[:100]}...")

        # Combine prompt and context for analysis
        full_text = prompt.lower()
        if additional_context:
            full_text += " " + additional_context.lower()

        # Initialize scoring
        scores = {intent: 0.0 for intent in PromptIntent}
        reasoning_parts = []
        extracted_info = {}

        # 1. Keyword-based scoring
        keyword_scores = self._score_keywords(full_text)
        for intent, score in keyword_scores.items():
            scores[intent] += score
            if score > 0:
                reasoning_parts.append(f"{intent.value}: {score:.2f} (keywords)")

        # 2. Pattern-based scoring
        pattern_scores = self._score_patterns(full_text)
        for intent, score in pattern_scores.items():
            scores[intent] += score
            if score > 0:
                reasoning_parts.append(f"{intent.value}: {score:.2f} (patterns)")

        # 3. Context-based scoring
        context_scores = self._score_context(
            prompt, additional_context, existing_endpoints
        )
        for intent, score in context_scores.items():
            scores[intent] += score
            if score > 0:
                reasoning_parts.append(f"{intent.value}: {score:.2f} (context)")

        # 4. Extract specific information
        extracted_info = self._extract_information(prompt, additional_context)

        # 5. Determine final intent and confidence
        max_intent = max(scores.items(), key=lambda x: x[1])
        intent = max_intent[0]
        confidence = min(max_intent[1] / 10.0, 1.0)  # Normalize to 0-1

        # Apply confidence thresholds and fallback logic
        if confidence < 0.3:
            intent = PromptIntent.UNCLEAR
            confidence = 0.0
            reasoning_parts.append("Low confidence - classified as unclear")

        reasoning = (
            "; ".join(reasoning_parts)
            if reasoning_parts
            else "No clear indicators found"
        )

        result = ClassificationResult(
            intent=intent,
            confidence=confidence,
            reasoning=reasoning,
            extracted_info=extracted_info,
        )

        logger.info(
            f"Classification result: {intent.value} (confidence: {confidence:.2f})"
        )
        return result

    def _score_keywords(self, text: str) -> Dict[PromptIntent, float]:
        """Score based on keyword presence"""
        scores = {}

        # Error/fix scoring
        error_count = sum(1 for keyword in self.error_keywords if keyword in text)
        scores[PromptIntent.FIX_ERROR] = error_count * 2.0

        # Creation scoring
        creation_count = sum(1 for keyword in self.creation_keywords if keyword in text)
        scores[PromptIntent.CREATE_NEW_ENDPOINT] = creation_count * 1.5

        # Update scoring
        update_count = sum(1 for keyword in self.update_keywords if keyword in text)
        scores[PromptIntent.UPDATE_EXISTING] = update_count * 1.8

        return scores

    def _score_patterns(self, text: str) -> Dict[PromptIntent, float]:
        """Score based on regex pattern matching"""
        scores = {intent: 0.0 for intent in PromptIntent}

        # Error patterns
        for pattern in self.error_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                scores[PromptIntent.FIX_ERROR] += 3.0

        # Creation patterns
        for pattern in self.creation_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                scores[PromptIntent.CREATE_NEW_ENDPOINT] += 2.5

        return scores

    def _score_context(
        self,
        prompt: str,
        additional_context: Optional[str],
        existing_endpoints: Optional[List[str]],
    ) -> Dict[PromptIntent, float]:
        """Score based on contextual information"""
        scores = {intent: 0.0 for intent in PromptIntent}

        # If there are existing endpoints mentioned
        if existing_endpoints:
            prompt_lower = prompt.lower()
            for endpoint in existing_endpoints:
                if endpoint.lower() in prompt_lower:
                    scores[PromptIntent.UPDATE_EXISTING] += 2.0
                    scores[PromptIntent.FIX_ERROR] += 1.5
                    break

        # Check for specific error indicators in context
        if additional_context:
            context_lower = additional_context.lower()
            if any(
                word in context_lower
                for word in ["stack trace", "error log", "exception"]
            ):
                scores[PromptIntent.FIX_ERROR] += 3.0

        return scores

    def _extract_information(
        self, prompt: str, additional_context: Optional[str]
    ) -> Dict[str, any]:
        """Extract specific information from the prompt"""
        info = {}

        # Extract HTTP methods
        http_methods = re.findall(
            r"\b(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\b", prompt, re.IGNORECASE
        )
        if http_methods:
            info["http_methods"] = list(set(method.upper() for method in http_methods))

        # Extract endpoint paths
        endpoint_paths = re.findall(r"/api/[^\s]+", prompt)
        if endpoint_paths:
            info["endpoint_paths"] = endpoint_paths

        # Extract entity names
        entity_patterns = [
            r"for\s+(\w+)",
            r"(\w+)\s+endpoint",
            r"manage\s+(\w+)",
            r"(\w+)\s+API",
        ]
        entities = []
        for pattern in entity_patterns:
            matches = re.findall(pattern, prompt, re.IGNORECASE)
            entities.extend(matches)

        if entities:
            info["potential_entities"] = list(set(entities))

        # Extract error types if mentioned
        error_types = re.findall(
            r"(4\d\d|5\d\d|syntax|import|runtime|logic)\s+error", prompt, re.IGNORECASE
        )
        if error_types:
            info["error_types"] = error_types

        return info

    def should_route_to_error_handler(
        self, classification: ClassificationResult
    ) -> bool:
        """Determine if the prompt should be routed to error correction handler"""
        return (
            classification.intent == PromptIntent.FIX_ERROR
            and classification.confidence > 0.6
        )

    def should_route_to_creation_handler(
        self, classification: ClassificationResult
    ) -> bool:
        """Determine if the prompt should be routed to new endpoint creation handler"""
        return (
            classification.intent == PromptIntent.CREATE_NEW_ENDPOINT
            and classification.confidence > 0.5
        )

    def should_route_to_update_handler(
        self, classification: ClassificationResult
    ) -> bool:
        """Determine if the prompt should be routed to update handler"""
        return (
            classification.intent == PromptIntent.UPDATE_EXISTING
            and classification.confidence > 0.6
        )
