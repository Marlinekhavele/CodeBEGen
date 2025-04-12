import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable
from langchain_core.callbacks.base import BaseCallbackHandler

logger = logging.getLogger(__name__)

class StreamingCallback(BaseCallbackHandler):
    """Custom callback handler for streaming LLM outputs"""
    
    def __init__(self, websocket=None):
        """Initialize with optional websocket for streaming to client"""
        self.websocket = websocket
        self.collected_content = ""
    
    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Process new tokens as they're generated"""
        self.collected_content += token
        
        # Stream to WebSocket if available
        if self.websocket and not self.websocket.closed:
            asyncio.create_task(self.websocket.send_text(token))
    
    def get_content(self) -> str:
        """Return the complete collected content"""
        return self.collected_content