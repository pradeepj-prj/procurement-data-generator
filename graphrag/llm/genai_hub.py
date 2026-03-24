"""SAP GenAI Hub client — wraps sap-ai-sdk-gen Orchestration V2 for chat completions."""

from __future__ import annotations

import os
from typing import Any, Generator

from graphrag.config import GraphRAGConfig


class GenAIHubClient:
    """Chat client using SAP GenAI Hub (Orchestration V2)."""

    def __init__(self, config: GraphRAGConfig) -> None:
        self._model_name = config.genai_model_name
        self._configure_env(config)
        self._service, self._model = self._create_service()

    @staticmethod
    def _configure_env(config: GraphRAGConfig) -> None:
        """Set env vars required by sap-ai-sdk-gen."""
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

    def _create_service(self) -> tuple[Any, Any]:
        from gen_ai_hub.orchestration_v2.service import OrchestrationService
        from gen_ai_hub.orchestration_v2.models.llm_model_details import LLMModelDetails

        service = OrchestrationService()
        model = LLMModelDetails(name=self._model_name)
        return service, model

    @staticmethod
    def _to_v2_messages(messages: list[dict]) -> list[Any]:
        """Convert OpenAI-style dicts to Orchestration V2 message objects."""
        from gen_ai_hub.orchestration_v2.models.message import (
            SystemMessage,
            UserMessage,
            AssistantMessage,
        )

        role_map = {
            "system": SystemMessage,
            "user": UserMessage,
            "assistant": AssistantMessage,
        }
        result = []
        for msg in messages:
            cls = role_map.get(msg["role"])
            if cls is None:
                raise ValueError(f"Unknown message role: {msg['role']}")
            result.append(cls(content=msg["content"]))
        return result

    def _build_config(self, messages: list[dict], stream: bool = False) -> Any:
        """Build OrchestrationConfig from message dicts."""
        from gen_ai_hub.orchestration_v2.models.template import (
            Template,
            PromptTemplatingModuleConfig,
        )
        from gen_ai_hub.orchestration_v2.models.config import (
            ModuleConfig,
            OrchestrationConfig,
        )

        v2_messages = self._to_v2_messages(messages)
        template = Template(template=v2_messages)
        ptmc = PromptTemplatingModuleConfig(prompt=template, model=self._model)
        module_config = ModuleConfig(prompt_templating=ptmc)

        kwargs: dict[str, Any] = {"modules": module_config}
        if stream:
            from gen_ai_hub.orchestration_v2.models.streaming import GlobalStreamOptions

            kwargs["stream"] = GlobalStreamOptions(enabled=True)

        return OrchestrationConfig(**kwargs)

    def chat(self, messages: list[dict]) -> str:
        """Send messages and return the assistant's reply."""
        config = self._build_config(messages)
        result = self._service.run(config=config)
        return result.final_result.choices[0].message.content

    def chat_stream(self, messages: list[dict]) -> Generator[str, None, None]:
        """Stream the assistant's reply token by token."""
        config = self._build_config(messages, stream=True)
        for chunk in self._service.stream(config=config):
            delta = chunk.final_result.choices[0].delta
            if delta.content:
                yield delta.content
