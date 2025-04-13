# app/api/v1/utils/streaming_callback.py

import logging
import asyncio
from typing import Dict, Any, Optional, List, Callable
from langchain_core.callbacks.base import BaseCallbackHandler

logger = logging.getLogger(__name__)

class StreamingCallback(BaseCallbackHandler):
    """Custom callback handler for streaming LLM outputs with WebSocket support"""
    
    def __init__(self, websocket=None, stage=None):
        """
        Initialize with optional websocket for streaming to client
        
        Args:
            websocket: WebSocket connection to stream tokens to
            stage: Current generation stage (endpoint, model, schema, helpers)
        """
        self.websocket = websocket
        self.stage = stage
        self.collected_content = ""
        self.token_count = 0
        self.streaming_started = False
    
    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Process new tokens as they're generated"""
        self.token_count += 1
        self.collected_content += token
        
        # Stream to WebSocket if available
        if self.websocket and not self.websocket.closed:
            try:
                # Create a task to send the token asynchronously
                # We can't directly await in this method as it's not an async method
                asyncio.create_task(self.websocket.send_text(token))
            except Exception as e:
                # Log the error but don't crash the token processing
                logger.error(f"Error sending token via WebSocket: {e}")
    
    async def send_stage_start(self):
        """Send a stage start message if this is configured with a stage"""
        if not self.stage or not self.websocket:
            return
            
        try:
            message = {
                "status": "token_stream_start",
                "stage": self.stage,
                "message": f"Streaming {self.stage} code generation..."
            }
            await self.websocket.send_json(message)
            self.streaming_started = True
        except Exception as e:
            logger.error(f"Error sending stage start message: {e}")
    
    def get_content(self) -> str:
        """Return the complete collected content"""
        return self.collected_content
    
    def get_token_count(self) -> int:
        """Return the number of tokens received"""
        return self.token_count