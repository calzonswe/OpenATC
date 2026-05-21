"""LLM service — interfaces with Ollama for ATC response generation."""

import json
import logging
from typing import AsyncGenerator, Optional

logger = logging.getLogger("openatc.llm")


class LLMService:
    """Generates ATC responses via Ollama.

    Supports streaming token-by-token for real-time feedback.
    """

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        host: str = "http://localhost:11434",
    ):
        self.model = model
        self.host = host
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import ollama
                self._client = ollama.AsyncClient(host=self.host)
            except ImportError:
                logger.error(
                    "ollama Python package not installed. Install with: "
                    "pip install ollama"
                )
                raise
        return self._client

    async def generate(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.2,
    ) -> AsyncGenerator[str, None]:
        """Stream a response from the LLM.

        Args:
            system_prompt: System-level instructions for the model
            messages: List of {"role": "user"|"assistant", "content": "..."} messages
            temperature: Sampling temperature (lower = more deterministic)

        Yields:
            Text tokens as they are generated
        """
        client = self._get_client()

        full_messages = [{"role": "system", "content": system_prompt}]
        full_messages.extend(messages)

        try:
            stream = await client.chat(
                model=self.model,
                messages=full_messages,
                stream=True,
                options={
                    "temperature": temperature,
                    "num_predict": 512,
                },
            )

            async for chunk in stream:
                if "message" in chunk and "content" in chunk["message"]:
                    token = chunk["message"]["content"]
                    if token:
                        yield token

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            yield f"[ATC communication error: {e}]"

    async def generate_sync(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.2,
    ) -> str:
        """Generate a complete response (non-streaming)."""
        parts = []
        async for token in self.generate(system_prompt, messages, temperature):
            parts.append(token)
        return "".join(parts)

    async def health(self) -> bool:
        """Check if Ollama is reachable and the model is available."""
        try:
            client = self._get_client()
            await client.list()
            return True
        except Exception:
            return False
