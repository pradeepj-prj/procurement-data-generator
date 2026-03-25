"""Lightweight tracing for the GraphRAG query pipeline."""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


# Entity ID patterns used to extract graph nodes from backend results
_ENTITY_ID_PATTERNS = [
    re.compile(r"VND-[\w-]+"),
    re.compile(r"PO-\d+"),
    re.compile(r"INV-\d+"),
    re.compile(r"CTR-[\w-]+"),
    re.compile(r"MAT-[\w-]+"),
    re.compile(r"GR-\d+"),
    re.compile(r"PAY-\d+"),
    re.compile(r"PR-\d+"),
]

# Known ID-bearing keys in backend results
_ID_KEYS = {
    "vendor_id", "material_id", "po_id", "contract_id", "invoice_id",
    "gr_id", "payment_id", "pr_id", "plant_id", "category_id",
    "vertex_id", "source_vertex", "target_vertex",
}

# Structural nesting: (container_key, edge_type, reverse)
# reverse=True means the child is the source (e.g. GR → PO, Invoice → PO)
_NESTED_EDGE_MAP = [
    ("vendor", "ORDERED_FROM", False),       # PO → Vendor
    ("materials", "CONTAINS_MATERIAL", False),  # PO → Material
    ("contract", "UNDER_CONTRACT", False),   # PO → Contract
    ("contracts", "HAS_CONTRACT", False),    # Vendor → Contract
    ("goods_receipts", "RECEIVED_FOR", True),  # GR → PO
    ("invoices", "INVOICED_FOR", True),      # Invoice → PO
    ("payments", "PAYS", True),              # Payment → Invoice
    ("po", "INVOICED_FOR", False),           # Invoice → PO (from invoice_context)
]

# Keys that indicate edge-like relationships between two entities
_EDGE_KEY_PAIRS = [
    ("vendor_id", "material_id", "SUPPLIES"),
    ("po_id", "vendor_id", "ORDERED_FROM"),
    ("po_id", "material_id", "CONTAINS_MATERIAL"),
    ("invoice_id", "po_id", "INVOICED_FOR"),
    ("gr_id", "po_id", "RECEIVED_FOR"),
    ("payment_id", "invoice_id", "PAYS"),
]


@dataclass
class Span:
    """A timed operation within the query pipeline."""

    name: str
    start_ms: float
    end_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    children: list[Span] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        return self.end_ms - self.start_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "start_ms": round(self.start_ms, 2),
            "end_ms": round(self.end_ms, 2),
            "duration_ms": round(self.duration_ms, 2),
            "metadata": self.metadata,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class QueryTrace:
    """Full trace of a single question through the pipeline."""

    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    question: str = ""
    total_ms: float = 0.0
    intent: dict[str, Any] = field(default_factory=dict)
    graph_nodes: list[str] = field(default_factory=list)
    graph_edges: list[dict[str, str]] = field(default_factory=list)
    spans: list[Span] = field(default_factory=list)
    context_snippet: str = ""
    llm_request: dict[str, Any] = field(default_factory=dict)
    llm_response: dict[str, Any] = field(default_factory=dict)
    pipeline: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "question": self.question,
            "total_ms": round(self.total_ms, 2),
            "intent": self.intent,
            "graph_nodes": self.graph_nodes,
            "graph_edges": self.graph_edges,
            "spans": [s.to_dict() for s in self.spans],
            "context_snippet": self.context_snippet,
            "llm_request": self.llm_request,
            "llm_response": self.llm_response,
            "pipeline": self.pipeline,
        }


def _now_ms() -> float:
    """Current time in milliseconds (monotonic)."""
    return time.perf_counter() * 1000


def _extract_ids_from_value(val: Any) -> list[str]:
    """Extract entity IDs from a single value."""
    if not isinstance(val, str):
        return []
    ids = []
    for pat in _ENTITY_ID_PATTERNS:
        ids.extend(pat.findall(val))
    return ids


def _extract_ids_from_result(result: Any) -> list[str]:
    """Recursively extract entity IDs from a backend result.

    Scans ALL string values for entity ID patterns (VND-*, PO-*, etc.),
    not just known key names, because backends return entities with generic
    "id" keys.
    """
    ids: list[str] = []
    if isinstance(result, dict):
        for val in result.values():
            if isinstance(val, str):
                ids.extend(_extract_ids_from_value(val))
            elif isinstance(val, (dict, list)):
                ids.extend(_extract_ids_from_result(val))
    elif isinstance(result, list):
        for item in result:
            ids.extend(_extract_ids_from_result(item))
    return ids


def _extract_edges_from_result(result: Any) -> list[dict[str, str]]:
    """Extract edge relationships from backend results.

    Uses two strategies:
    1. Key-pair co-occurrence (e.g. vendor_id + material_id in same dict)
    2. Structural nesting (e.g. PO dict contains "vendor" sub-dict with its own ID)
    """
    edges: list[dict[str, str]] = []
    if isinstance(result, dict):
        # Strategy 1: key pairs at the same level
        for src_key, tgt_key, edge_type in _EDGE_KEY_PAIRS:
            src = result.get(src_key)
            tgt = result.get(tgt_key)
            if src and tgt and isinstance(src, str) and isinstance(tgt, str):
                edges.append({"source": src, "target": tgt, "edge_type": edge_type})

        # Strategy 2: structural nesting — parent entity contains child entities
        parent_id = result.get("id", "")
        if parent_id and isinstance(parent_id, str):
            for container_key, edge_type, reverse in _NESTED_EDGE_MAP:
                child = result.get(container_key)
                if child is None:
                    continue
                children = child if isinstance(child, list) else [child]
                for c in children:
                    if isinstance(c, dict):
                        child_id = c.get("id", "")
                        if child_id and isinstance(child_id, str):
                            if reverse:
                                edges.append({"source": child_id, "target": parent_id, "edge_type": edge_type})
                            else:
                                edges.append({"source": parent_id, "target": child_id, "edge_type": edge_type})

        # Recurse into all nested structures
        for val in result.values():
            if isinstance(val, (dict, list)):
                edges.extend(_extract_edges_from_result(val))
    elif isinstance(result, list):
        for item in result:
            edges.extend(_extract_edges_from_result(item))
    return edges


# Protocol method names to intercept in the proxy
_PROTOCOL_METHODS = {
    "get_entity_by_id", "get_vendor_profile", "get_vendor_materials",
    "get_material_vendors", "get_po_details", "get_p2p_chain",
    "get_contract_pos", "get_vendor_contracts", "get_invoices_with_issues",
    "get_invoice_context", "get_plant_materials", "get_vendor_pos",
    "get_category_tree", "get_vendor_plant_contracts", "search_entities",
    "get_summary",
    # Phase 2 relational methods
    "get_spend_by_vendor", "get_spend_by_category", "get_pos_by_filter",
    "get_invoice_aging", "get_overdue_invoices", "get_vendor_risk_summary",
}


class TracingBackendProxy:
    """Wraps a GraphBackend to record spans and extract entity IDs.

    Uses __getattr__ to intercept protocol method calls without modifying
    the backend or the Protocol definition. Only intercepts known protocol
    methods to avoid interfering with dunder methods.
    """

    def __init__(self, backend: Any, parent_span: Span) -> None:
        self._backend = backend
        self._parent_span = parent_span
        self.graph_nodes: list[str] = []
        self.graph_edges: list[dict[str, str]] = []

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._backend, name)
        if name not in _PROTOCOL_METHODS or not callable(attr):
            return attr

        def traced_call(*args: Any, **kwargs: Any) -> Any:
            span = Span(name=f"retrieve.{name}", start_ms=_now_ms())
            try:
                result = attr(*args, **kwargs)

                # Count results
                if isinstance(result, list):
                    span.metadata["row_count"] = len(result)
                elif isinstance(result, dict):
                    span.metadata["row_count"] = 1 if result else 0

                # Record call params
                if args:
                    span.metadata["params"] = [str(a) for a in args]

                # Extract entity IDs and edges
                ids = _extract_ids_from_result(result)
                self.graph_nodes.extend(ids)

                edges = _extract_edges_from_result(result)
                self.graph_edges.extend(edges)

                return result
            finally:
                span.end_ms = _now_ms()
                self._parent_span.children.append(span)

        return traced_call


class TracingLLMProxy:
    """Wraps a GenAIHubClient to record timing, token estimates, and pipeline details."""

    def __init__(self, llm: Any) -> None:
        self._llm = llm
        self.pipeline_details: dict[str, Any] = {}

    @property
    def model_name(self) -> str:
        return getattr(self._llm, "model_name", "unknown")

    def chat(self, messages: list[dict], span: Span | None = None) -> str:
        """Call chat() and record metadata in the provided span.

        Uses chat_with_pipeline() if available to capture masking/filtering
        details; falls back to plain chat() for mock LLMs in tests.
        """
        start = _now_ms()

        if hasattr(self._llm, "chat_with_pipeline"):
            result, details = self._llm.chat_with_pipeline(messages)
            self.pipeline_details = details.to_dict()
        else:
            result = self._llm.chat(messages)

        elapsed = _now_ms() - start

        if span is not None:
            prompt_chars = sum(len(m.get("content", "")) for m in messages)
            span.metadata.update({
                "model": self.model_name,
                "message_count": len(messages),
                "estimated_prompt_tokens": prompt_chars // 4,
                "estimated_response_tokens": len(result) // 4,
                "latency_ms": round(elapsed, 2),
            })

        return result

    def chat_stream(self, messages: list[dict]) -> Any:
        """Pass through to underlying stream (no wrapping needed for spans)."""
        return self._llm.chat_stream(messages)
