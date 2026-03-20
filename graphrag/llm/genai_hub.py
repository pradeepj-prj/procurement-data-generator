"""SAP GenAI Hub client — wraps generative-ai-hub-sdk for chat completions."""

from __future__ import annotations

import os
from typing import Any, Generator

from graphrag.config import GraphRAGConfig


class GenAIHubClient:
    """Chat client using SAP GenAI Hub (OpenAI-compatible proxy)."""

    def __init__(self, config: GraphRAGConfig) -> None:
        self._model = config.genai_model_name
        self._configure_env(config)
        self._client = self._create_client()

    @staticmethod
    def _configure_env(config: GraphRAGConfig) -> None:
        """Set env vars required by gen_ai_hub SDK."""
        env_map = {
            "AICORE_AUTH_URL": config.aicore_auth_url,
            "AICORE_CLIENT_ID": config.aicore_client_id,
            "AICORE_CLIENT_SECRET": config.aicore_client_secret,
            "AICORE_RESOURCE_GROUP": config.aicore_resource_group,
            "AICORE_BASE_URL": config.aicore_base_url,
        }
        for key, val in env_map.items():
            if val:
                os.environ.setdefault(key, val)

    def _create_client(self) -> Any:
        from gen_ai_hub.proxy.native.openai import OpenAI

        return OpenAI()

    def chat(self, messages: list[dict]) -> str:
        """Send messages and return the assistant's reply."""
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
        )
        return response.choices[0].message.content

    def chat_stream(self, messages: list[dict]) -> Generator[str, None, None]:
        """Stream the assistant's reply token by token."""
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            stream=True,
        )
        for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
