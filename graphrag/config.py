"""GraphRAG configuration — loads from .env, supports HANA + NetworkX backends."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from graphrag.backends.protocol import GraphBackend

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_env() -> None:
    """Load .env file into os.environ (does not override existing vars)."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


@dataclass
class GraphRAGConfig:
    """All GraphRAG settings — HANA, NetworkX, and GenAI Hub."""

    # Backend selector
    graph_backend: str = "hana"

    # HANA Cloud
    hana_host: str = ""
    hana_port: int = 443
    hana_user: str = "DBADMIN"
    hana_password: str = ""
    hana_schema: str = "PROCUREMENT"

    # NetworkX backend
    csv_dir: str = "output/csv"
    graph_pickle: str = "output/graph.pkl"

    # SAP GenAI Hub
    aicore_auth_url: str = ""
    aicore_client_id: str = ""
    aicore_client_secret: str = ""
    aicore_resource_group: str = "default"
    aicore_base_url: str = ""
    genai_model_name: str = "gpt-4o"

    @classmethod
    def from_env(cls) -> GraphRAGConfig:
        """Build config from environment variables."""
        load_env()
        return cls(
            graph_backend=os.environ.get("GRAPH_BACKEND", "hana"),
            hana_host=os.environ.get("HANA_HOST", ""),
            hana_port=int(os.environ.get("HANA_PORT", "443")),
            hana_user=os.environ.get("HANA_USER", "DBADMIN"),
            hana_password=os.environ.get("HANA_PASSWORD", ""),
            hana_schema=os.environ.get("HANA_SCHEMA", "PROCUREMENT"),
            csv_dir=os.environ.get("CSV_DIR", "output/csv"),
            graph_pickle=os.environ.get("GRAPH_PICKLE", "output/graph.pkl"),
            aicore_auth_url=os.environ.get("AICORE_AUTH_URL", ""),
            aicore_client_id=os.environ.get("AICORE_CLIENT_ID", ""),
            aicore_client_secret=os.environ.get("AICORE_CLIENT_SECRET", ""),
            aicore_resource_group=os.environ.get("AICORE_RESOURCE_GROUP", "default"),
            aicore_base_url=os.environ.get("AICORE_BASE_URL", ""),
            genai_model_name=os.environ.get("GENAI_MODEL_NAME", "gpt-4o"),
        )


def get_backend(config: GraphRAGConfig | None = None) -> GraphBackend:
    """Factory — returns the correct backend based on config."""
    if config is None:
        config = GraphRAGConfig.from_env()

    if config.graph_backend == "networkx":
        from graphrag.backends.networkx_backend import NetworkXGraphBackend

        return NetworkXGraphBackend(config)
    elif config.graph_backend == "hana":
        from graphrag.backends.hana_backend import HanaGraphBackend

        return HanaGraphBackend(config)
    else:
        raise ValueError(f"Unknown backend: {config.graph_backend!r} (use 'hana' or 'networkx')")
