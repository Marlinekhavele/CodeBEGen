import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def extract_entity_from_code(code: str, language: str = "python") -> Optional[str]:
    """
    Extract the main entity name from code in different programming languages.
    
    Args:
        code: The code to analyze
        language: The programming language of the code (python, javascript, etc.)
        
    Returns:
        The extracted entity name or None if not found
    """
    if not code or not isinstance(code, str):
        logger.warning("No code provided for entity extraction")
        return None
    
    language = language.lower()
    
    try:
        if language == "python":
            return extract_entity_from_python(code)
        elif language in ["javascript", "js"]:
            return extract_entity_from_javascript(code)
        elif language == "java":
            return extract_entity_from_java(code)
        else:
            # Default to a generic extraction method
            return extract_entity_generic(code)
    except Exception as e:
        logger.error(f"Error extracting entity from {language} code: {e}", exc_info=True)
        return None

def extract_entity_from_python(code: str) -> Optional[str]:
    """Extract the main entity name from Python code"""
    # Try to find model imports
    model_import = re.search(r'from\s+models\.(\w+)\s+import\s+(\w+)', code)
    if model_import:
        return model_import.group(2)
    
    # Try to find model usage
    model_usage = re.search(r'db\.query\((\w+)\)', code)
    if model_usage:
        return model_usage.group(1)
    
    # Try to find schema imports
    schema_import = re.search(r'from\s+schemas\.(\w+)\s+import\s+(\w+)Schema', code)
    if schema_import:
        return schema_import.group(2)
    
    # Look for helper function imports that might contain entity names
    helper_import = re.search(r'from\s+helpers\.(\w+)_helpers\s+import', code)
    if helper_import:
        # Convert snake_case to PascalCase if needed
        entity = helper_import.group(1)
        return ''.join(word.capitalize() for word in entity.split('_'))
    
    # Look for route paths that might indicate the entity
    route_path = re.search(r'@router\.\w+\([\'"]/?(\w+)[\'"]', code)
    if route_path:
        # Convert plural to singular if needed
        entity = route_path.group(1)
        if entity.endswith('s'):
            entity = entity[:-1]
        return entity.capitalize()
    
    return None

def extract_entity_from_javascript(code: str) -> Optional[str]:
    """Extract the main entity name from JavaScript code"""
    # Try to find model imports
    model_import = re.search(r'const\s+(\w+)\s+=\s+require\([\'"]\.\.\/models\/(\w+)[\'"]', code)
    if model_import:
        return model_import.group(1)
    
    # Try to find model usage in Mongoose
    mongoose_model = re.search(r'const\s+(\w+)Schema\s+=\s+new\s+Schema', code)
    if mongoose_model:
        return mongoose_model.group(1)
    
    # Try to find model usage in Sequelize
    sequelize_model = re.search(r'class\s+(\w+)\s+extends\s+Model', code)
    if sequelize_model:
        return sequelize_model.group(1)
    
    # Try to find helper function imports
    helper_import = re.search(r'const\s+{\s*.*\s*}\s+=\s+require\([\'"]\.\.\/helpers\/(\w+)Helpers[\'"]', code)
    if helper_import:
        # Get entity name from helperName
        entity = helper_import.group(1)
        return entity
    
    # Look for route paths that might indicate the entity
    route_path = re.search(r'router\.\w+\([\'"]/?(\w+)[\'"]', code)
    if route_path:
        # Convert plural to singular if needed
        entity = route_path.group(1)
        if entity.endswith('s'):
            entity = entity[:-1]
        return entity.charAt(0).toUpperCase() + entity.slice(1)
    
    return None

def extract_entity_from_java(code: str) -> Optional[str]:
    """Extract the main entity name from Java code"""
    # Try to find class definition
    class_def = re.search(r'public\s+class\s+(\w+)', code)
    if class_def:
        class_name = class_def.group(1)
        if class_name.endswith("Controller") or class_name.endswith("Service") or class_name.endswith("Repository"):
            # Extract the entity name from the class name
            if class_name.endswith("Controller"):
                return class_name.replace("Controller", "")
            elif class_name.endswith("Service"):
                return class_name.replace("Service", "")
            elif class_name.endswith("Repository"):
                return class_name.replace("Repository", "")
        return class_name
    
    # Try to find entity in annotations
    entity_annotation = re.search(r'@Entity\s+public\s+class\s+(\w+)', code)
    if entity_annotation:
        return entity_annotation.group(1)
    
    # Try to find entity in method parameters
    method_params = re.search(r'public\s+\w+\s+\w+\((\w+)\s+(\w+)', code)
    if method_params:
        param_type = method_params.group(1)
        if not param_type.startsWith("String") and not param_type.startsWith("int") and not param_type.startsWith("boolean"):
            return param_type
    
    # Look for entity name in REST mappings
    rest_mapping = re.search(r'@\w+Mapping\([\'"]/?(\w+)[\'"]', code)
    if rest_mapping:
        entity = rest_mapping.group(1)
        if entity.endsWith("s"):
            entity = entity[:-1]
        return entity.charAt(0).toUpperCase() + entity.slice(1)
    
    return None

def extract_entity_generic(code: str) -> Optional[str]:
    """Generic method to extract entity name from code in any language"""
    # Try to identify entity name from file operations or database references
    patterns = [
        # Models/entities
        r'(?:class|type|interface)\s+(\w+)(?:Model|Entity|Schema)?',
        # Database operations
        r'(?:from|table|collection)\s+[\'"]?(\w+)[\'"]?',
        # API routes
        r'(?:route|path|mapping).*?[\'"]/?(\w+)[\'"]',
        # Functions that likely operate on entities
        r'(?:get|create|update|delete|find)(\w+)(?:ById|ByName|All)?'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, code, re.IGNORECASE)
        if match:
            entity = match.group(1)
            # Clean up common prefixes/suffixes
            for suffix in ['s', 'Model', 'Entity', 'Schema', 'Controller', 'Service', 'Repository']:
                if entity.endswith(suffix):
                    entity = entity[:-len(suffix)]
            return entity
    
    return None