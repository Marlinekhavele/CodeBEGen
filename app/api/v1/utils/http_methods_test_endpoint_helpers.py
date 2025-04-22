"""
Helper utilities for API endpoint testing.

This module provides utility functions for handling API endpoint testing operations, including:
- Adding authentication to requests
- Applying environment variables to request payloads
- Saving requests to storage
- Tracking request history

In a production environment, the in-memory data structures should be replaced with database operations.
"""
from typing import Dict, Any
from app.api.v1.models.http_methods_test_endpoint import AuthType

# You can either import these from the main module or define them here
# These references to global storage could be replaced with a database in production

def add_auth_to_request(request_kwargs: Dict, auth: Any) -> Dict:
    """
    Add authentication details to a request.
    
    Supports three authentication types:
    - Basic: Username and password authentication
    - Bearer: Token-based authentication
    - API Key: Key-value pair added to either header or query parameters
    
    Parameters:
    -----------
    request_kwargs : Dict
        Dictionary of request keyword arguments to be modified
    auth : Any
        Authentication object containing authentication details
        
    Returns:
    --------
    Dict
        Modified request_kwargs with authentication details added
        
    Notes:
    ------
    The auth object must have a 'type' attribute matching one of the AuthType enum values.
    """
    if auth.type == AuthType.BASIC and auth.username and auth.password:
        request_kwargs["auth"] = (auth.username, auth.password)
    
    elif auth.type == AuthType.BEARER and auth.token:
        if "headers" not in request_kwargs:
            request_kwargs["headers"] = {}
        request_kwargs["headers"]["Authorization"] = f"Bearer {auth.token}"
    
    elif auth.type == AuthType.API_KEY and auth.key_name and auth.key_value:
        if auth.add_to == "header":
            if "headers" not in request_kwargs:
                request_kwargs["headers"] = {}
            request_kwargs["headers"][auth.key_name] = auth.key_value
        else:  # query
            if "params" not in request_kwargs:
                request_kwargs["params"] = {}
            request_kwargs["params"][auth.key_name] = auth.key_value
    
    return request_kwargs
