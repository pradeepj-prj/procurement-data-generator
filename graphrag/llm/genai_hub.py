"""SAP GenAI Hub client — wraps sap-ai-sdk-gen Orchestration V2 for chat completions.

Includes content filtering (Azure Content Safety) and data masking (SAP DPI)
as part of the orchestration pipeline.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Generator

from graphrag.config import GraphRAGConfig

# Singapore NRIC/FIN pattern: [STFGM] + 7 digits + 1 letter
_NRIC_PATTERN = re.compile(r"\b[STFGM]\d{7}[A-Z]\b", re.IGNORECASE)


@dataclass
class PipelineDetails:
    """Captures masking and filtering details from a single LLM call."""

    # Data masking
    original_query: str = ""
    masked_query: str = ""
    entities_masked: list[str] = field(default_factory=list)
    client_side_masked: bool = False

    # Content filtering
    input_filter: dict[str, Any] = field(default_factory=dict)
    output_filter: dict[str, Any] = field(default_factory=dict)
    blocked: bool = False
    blocked_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_masking": {
                "original_query": self.original_query,
                "masked_query": self.masked_query,
                "entities_masked": self.entities_masked,
                "client_side_masked": self.client_side_masked,
            },
            "content_filtering": {
                "input": self.input_filter,
                "output": self.output_filter,
                "blocked": self.blocked,
                "blocked_by": self.blocked_by,
            },
        }


def mask_nric(text: str) -> tuple[str, list[str]]:
    """Replace Singapore NRIC/FIN numbers with MASKED_NRIC.

    NRIC format: [STFGM] prefix + 7 digits + check letter.
    Returns (masked_text, list_of_entity_types_found).
    """
    entities: list[str] = []
    if _NRIC_PATTERN.search(text):
        text = _NRIC_PATTERN.sub("MASKED_NRIC", text)
        entities.append("NRIC")
    return text, entities


class GenAIHubClient:
    """Chat client using SAP GenAI Hub (Orchestration V2).

    Pipeline: client-side NRIC masking → DPI masking (15 entity types)
    → input content filtering → LLM → output content filtering.
    """

    def __init__(self, config: GraphRAGConfig) -> None:
        self._model_name = config.genai_model_name
        self._configure_env(config)
        self._service, self._model = self._create_service()

    @property
    def model_name(self) -> str:
        return self._model_name

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

    @staticmethod
    def _create_content_filter() -> Any:
        """Create Azure Content Safety filter config for input and output."""
        from gen_ai_hub.orchestration_v2.models.content_filtering import (
            ContentFilter,
            FilteringModuleConfig,
            InputFiltering,
            OutputFiltering,
        )
        from gen_ai_hub.orchestration_v2.models.azure_content_filter import (
            AzureContentFilter,
            AzureThreshold,
        )

        azure_filter = AzureContentFilter(
            hate=AzureThreshold.ALLOW_SAFE,
            violence=AzureThreshold.ALLOW_SAFE_LOW,
            self_harm=AzureThreshold.ALLOW_SAFE_LOW_MEDIUM,
            sexual=AzureThreshold.ALLOW_SAFE_LOW_MEDIUM,
        )
        content_filter = ContentFilter(filters=[azure_filter])

        return FilteringModuleConfig(
            input=InputFiltering(filters=[content_filter]),
            output=OutputFiltering(filters=[content_filter]),
        )

    @staticmethod
    def _create_data_masking() -> Any:
        """Create DPI masking config for 15 PII entity types."""
        from gen_ai_hub.orchestration_v2.models.data_masking import (
            MaskingModuleConfig,
            MaskingProviderConfig,
            MaskingMethod,
            DPIStandardEntity,
            ProfileEntity,
        )

        entities = [
            DPIStandardEntity(type=ProfileEntity.PERSON),
            DPIStandardEntity(type=ProfileEntity.ORG),
            DPIStandardEntity(type=ProfileEntity.EMAIL),
            DPIStandardEntity(type=ProfileEntity.PHONE),
            DPIStandardEntity(type=ProfileEntity.ADDRESS),
            DPIStandardEntity(type=ProfileEntity.USERNAME_PASSWORD),
            DPIStandardEntity(type=ProfileEntity.SAP_IDS_INTERNAL),
            DPIStandardEntity(type=ProfileEntity.SAP_IDS_PUBLIC),
            DPIStandardEntity(type=ProfileEntity.NATIONAL_ID),
            DPIStandardEntity(type=ProfileEntity.SSN),
            DPIStandardEntity(type=ProfileEntity.PASSPORT),
            DPIStandardEntity(type=ProfileEntity.DRIVING_LICENSE),
            DPIStandardEntity(type=ProfileEntity.IBAN),
            DPIStandardEntity(type=ProfileEntity.CREDIT_CARD_NUMBER),
            DPIStandardEntity(type=ProfileEntity.SENSITIVE_DATA),
        ]

        return MaskingModuleConfig(
            masking_providers=[
                MaskingProviderConfig(
                    method=MaskingMethod.ANONYMIZATION,
                    entities=entities,
                )
            ]
        )

    def _build_config(self, messages: list[dict], stream: bool = False) -> Any:
        """Build OrchestrationConfig with filtering and masking modules."""
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
        module_config = ModuleConfig(
            prompt_templating=ptmc,
            filtering=self._create_content_filter(),
            masking=self._create_data_masking(),
        )

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

    def chat_with_pipeline(
        self, messages: list[dict]
    ) -> tuple[str, PipelineDetails]:
        """Send messages and return reply + pipeline details (masking/filtering)."""
        details = PipelineDetails()

        # Client-side NRIC masking on user messages
        masked_messages = []
        for msg in messages:
            if msg["role"] == "user":
                original = msg["content"]
                masked_text, entities = mask_nric(original)
                if entities:
                    details.original_query = original
                    details.masked_query = masked_text
                    details.entities_masked.extend(entities)
                    details.client_side_masked = True
                    masked_messages.append({**msg, "content": masked_text})
                else:
                    if not details.original_query:
                        details.original_query = original
                        details.masked_query = original
                    masked_messages.append(msg)
            else:
                masked_messages.append(msg)

        config = self._build_config(masked_messages)

        try:
            result = self._service.run(config=config)
            answer = result.final_result.choices[0].message.content

            # Content filtering scores are available but not always exposed
            # in the same way across SDK versions. We record what we can.
            details.input_filter = {"passed": True}
            details.output_filter = {"passed": True}

            return answer, details

        except Exception as exc:
            exc_str = str(exc).lower()
            if "content_filter" in exc_str or "filtering" in exc_str:
                details.blocked = True
                details.blocked_by = "content_filtering"
            elif "masking" in exc_str:
                details.blocked = True
                details.blocked_by = "masking"
            else:
                raise
            return (
                "Your query was blocked by the content safety pipeline. "
                "Please rephrase your question.",
                details,
            )

    def chat_stream(self, messages: list[dict]) -> Generator[str, None, None]:
        """Stream the assistant's reply token by token."""
        # Apply client-side NRIC masking for streaming too
        masked_messages = []
        for msg in messages:
            if msg["role"] == "user":
                masked_text, _ = mask_nric(msg["content"])
                masked_messages.append({**msg, "content": masked_text})
            else:
                masked_messages.append(msg)

        config = self._build_config(masked_messages, stream=True)
        for chunk in self._service.stream(config=config):
            delta = chunk.final_result.choices[0].delta
            if delta.content:
                yield delta.content
