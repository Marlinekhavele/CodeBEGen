import asyncio
import logging

from langchain_core.callbacks.base import BaseCallbackHandler

logger = logging.getLogger(__name__)


class StreamingCallback(BaseCallbackHandler):
    """Custom callback handler for streaming LLM outputs with WebSocket support"""

    def __init__(self, websocket=None, stage=None):
        """
        Initialize with optional websocket for streaming to client

        Args:
            websocket: WebSocket connection to stream tokens to
            stage: Current generation stage (endpoint, model, schema, helpers)"""
        self.websocket = websocket
        self.stage = stage
        self.collected_content = ""
        self.token_count = 0
        self.streaming_started = False
        self.started = False
        self.ended = False

    def on_llm_start(self, serialized, prompts, **kwargs):
        """Called when LLM starts processing"""
        self.started = True
        logger.info(f"LLM started processing with {len(prompts)} prompt(s)")

    def on_llm_end(self, response, **kwargs):
        """Called when LLM finishes processing"""
        self.ended = True
        logger.info(f"LLM finished processing. Generated {self.token_count} tokens")

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Process new tokens as they're generated"""
        self.token_count += 1
        self.collected_content += token

        # Stream to WebSocket if available
        if self.websocket and self._is_websocket_connected():
            try:
                # Use a more reliable method to send tokens
                # Get the current event loop and run the coroutine
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're already in an async context, schedule the coroutine
                    loop.create_task(self._send_token_async(token))
                else:
                    # If no loop is running, run it synchronously
                    asyncio.run(self._send_token_async(token))
            except Exception as e:
                # Log the error but don't crash the token processing
                logger.error(f"Error sending token via WebSocket: {e}")

    async def _send_token_async(self, token: str):
        """Helper method to send token asynchronously"""
        try:
            if self.websocket and not self.websocket.closed:
                await self.websocket.send_text(token)
        except Exception as e:
            logger.error(f"Failed to send token: {e}")

    async def send_stage_start(self):
        """Send a stage start message if this is configured with a stage"""
        if not self.stage or not self.websocket:
            return

        try:
            message = {
                "status": "token_stream_start",
                "stage": self.stage,
                "message": f"Streaming {self.stage} code generation...",
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

    def _is_websocket_connected(self) -> bool:
        """Check if WebSocket is connected and ready"""
        try:
            return (
                self.websocket is not None
                and hasattr(self.websocket, "closed")
                and not self.websocket.closed
            )
        except Exception:
            return False
