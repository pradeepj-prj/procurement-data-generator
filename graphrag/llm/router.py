"""Intent router — classifies questions and routes to the right graph query."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from graphrag.backends.protocol import GraphBackend
from graphrag.llm.genai_hub import GenAIHubClient
from graphrag.llm.prompts import build_rag_messages, build_router_messages
from graphrag.observability.trace import (
    QueryTrace,
    Span,
    TracingBackendProxy,
    TracingLLMProxy,
    _now_ms,
)
from graphrag.retrieval import context_formatter as fmt


@dataclass
class QueryIntent:
    """Classified intent with pattern name and extracted IDs."""

    pattern: str
    entity_id: str | None = None
    entity_type: str | None = None
    search_query: str | None = None
    filter_params: dict | None = None


class IntentRouter:
    """Classifies user questions and routes them to graph queries."""

    def __init__(self, backend: GraphBackend, llm: GenAIHubClient) -> None:
        self._backend = backend
        self._llm = llm

    def classify(self, question: str) -> QueryIntent:
        """Use LLM to classify the question into a query pattern."""
        messages = build_router_messages(question)
        response = self._llm.chat(messages)

        try:
            # Strip markdown fences if present
            cleaned = response.strip()
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            data = json.loads(cleaned)
            return QueryIntent(
                pattern=data.get("pattern", "search"),
                entity_id=data.get("entity_id"),
                entity_type=data.get("entity_type"),
                search_query=data.get("search_query"),
                filter_params=data.get("filter_params"),
            )
        except (json.JSONDecodeError, KeyError):
            # Fallback: try to extract entity IDs from the question
            return self._fallback_classify(question)

    def _fallback_classify(self, question: str) -> QueryIntent:
        """Rule-based fallback when LLM classification fails."""
        q = question.lower()

        # Try to extract entity IDs
        id_patterns = [
            (r"VND-[\w-]+", "vendor_profile"),
            (r"PO-\d+", "p2p_chain"),
            (r"INV-\d+", "invoice_context"),
            (r"CTR-\d+", "contract_pos"),
            (r"MAT-[\w-]+", "material_vendors"),
            (r"GR-\d+", "entity_lookup"),
            (r"PAY-\d+", "entity_lookup"),
            (r"PR-\d+", "entity_lookup"),
        ]
        for pattern, query_pattern in id_patterns:
            match = re.search(pattern, question, re.IGNORECASE)
            if match:
                return QueryIntent(
                    pattern=query_pattern,
                    entity_id=match.group(0),
                )

        # Keyword-based fallback
        if "invoice" in q and ("issue" in q or "problem" in q or "mismatch" in q):
            return QueryIntent(pattern="invoice_issues")
        if "spend" in q and "vendor" in q:
            return QueryIntent(pattern="spend_by_vendor")
        if "spend" in q and "categor" in q:
            return QueryIntent(pattern="spend_by_category")
        if "maverick" in q or ("filter" in q and "po" in q):
            fp: dict[str, Any] = {}
            if "maverick" in q:
                fp["maverick"] = True
            return QueryIntent(pattern="po_filter", filter_params=fp)
        if "aging" in q:
            return QueryIntent(pattern="invoice_aging")
        if "overdue" in q or "past due" in q:
            return QueryIntent(pattern="overdue_invoices")
        if "risk" in q and "vendor" in q:
            return QueryIntent(pattern="vendor_risk")
        if "summary" in q or "overview" in q:
            return QueryIntent(pattern="summary")

        return QueryIntent(pattern="search", search_query=question)

    def retrieve(self, intent: QueryIntent, backend: Any = None) -> str:
        """Execute the graph query for a classified intent and format results."""
        b = backend or self._backend
        eid = intent.entity_id

        match intent.pattern:
            case "entity_lookup":
                data = b.get_entity_by_id(eid) if eid else {}
                return fmt.format_entity(data)
            case "vendor_profile":
                data = b.get_vendor_profile(eid) if eid else {}
                return fmt.format_vendor_profile(data)
            case "vendor_materials":
                items = b.get_vendor_materials(eid) if eid else []
                return fmt.format_list(items, "Vendor Materials")
            case "material_vendors":
                items = b.get_material_vendors(eid) if eid else []
                return fmt.format_list(items, "Material Vendors")
            case "po_details":
                data = b.get_po_details(eid) if eid else {}
                return fmt.format_p2p_chain(data)
            case "p2p_chain":
                data = b.get_p2p_chain(eid) if eid else {}
                return fmt.format_p2p_chain(data)
            case "contract_pos":
                items = b.get_contract_pos(eid) if eid else []
                return fmt.format_list(items, "Contract POs")
            case "vendor_contracts":
                items = b.get_vendor_contracts(eid) if eid else []
                return fmt.format_list(items, "Vendor Contracts")
            case "invoice_issues":
                items = b.get_invoices_with_issues()
                return fmt.format_list(items, "Invoices with Issues")
            case "invoice_context":
                data = b.get_invoice_context(eid) if eid else {}
                return fmt.format_invoice_context(data)
            case "plant_materials":
                items = b.get_plant_materials(eid) if eid else []
                return fmt.format_list(items, "Plant Materials")
            case "vendor_pos":
                items = b.get_vendor_pos(eid) if eid else []
                return fmt.format_list(items, "Vendor POs")
            case "category_tree":
                data = b.get_category_tree(eid) if eid else {}
                return fmt.format_category_tree(data)
            case "vendor_plant_contracts":
                items = b.get_vendor_plant_contracts(eid) if eid else []
                return fmt.format_vendor_plant_contracts(items)
            case "summary":
                data = b.get_summary()
                return fmt.format_entity(data)
            case "spend_by_vendor":
                items = b.get_spend_by_vendor(top_n=10)
                return fmt.format_spend_table(items, "Top Vendors by Spend")
            case "spend_by_category":
                items = b.get_spend_by_category(top_n=10)
                return fmt.format_spend_table(items, "Spend by Category")
            case "po_filter":
                fp = intent.filter_params or {}
                items = b.get_pos_by_filter(
                    status=fp.get("status"),
                    maverick=fp.get("maverick"),
                    min_value=fp.get("min_value"),
                    max_value=fp.get("max_value"),
                )
                return fmt.format_po_list(items)
            case "invoice_aging":
                items = b.get_invoice_aging()
                return fmt.format_invoice_aging(items)
            case "overdue_invoices":
                items = b.get_overdue_invoices()
                return fmt.format_po_list(items)
            case "vendor_risk":
                items = b.get_vendor_risk_summary()
                return fmt.format_vendor_risk(items)
            case "search" | _:
                query = intent.search_query or (eid if eid else "")
                items = b.search_entities(query, intent.entity_type)
                return fmt.format_search_results(items)

    def route_and_retrieve(self, question: str) -> str:
        """Classify → query → format (single call)."""
        intent = self.classify(question)
        return self.retrieve(intent)

    def answer(self, question: str, history: list[dict] | None = None) -> dict:
        """Full RAG pipeline: classify → retrieve → generate answer."""
        intent = self.classify(question)
        context = self.retrieve(intent)

        messages = build_rag_messages(question, context, history)
        answer = self._llm.chat(messages)

        # Extract referenced entity IDs from the answer
        sources = _extract_entity_ids(answer)

        return {
            "answer": answer,
            "sources": sources,
            "query_pattern": intent.pattern,
            "context_snippet": context[:500],
        }

    def answer_with_trace(
        self, question: str, history: list[dict] | None = None
    ) -> tuple[dict, QueryTrace]:
        """Full RAG pipeline with structured tracing."""
        trace = QueryTrace(question=question)
        overall_start = _now_ms()

        # ── Classify ────────────────────────────────────────────────────
        classify_span = Span(name="classify", start_ms=_now_ms())
        intent = self.classify(question)
        classify_span.end_ms = _now_ms()
        classify_span.metadata = {
            "pattern": intent.pattern,
            "entity_id": intent.entity_id,
            "entity_type": intent.entity_type,
            "search_query": intent.search_query,
        }
        trace.intent = classify_span.metadata.copy()
        trace.spans.append(classify_span)

        # ── Retrieve ────────────────────────────────────────────────────
        retrieve_span = Span(name="retrieve", start_ms=_now_ms())
        proxy = TracingBackendProxy(self._backend, retrieve_span)
        context = self.retrieve(intent, backend=proxy)
        retrieve_span.end_ms = _now_ms()
        retrieve_span.metadata["backend_calls"] = len(retrieve_span.children)

        # Deduplicate graph nodes and edges
        trace.graph_nodes = sorted(set(proxy.graph_nodes))
        seen_edges: set[tuple[str, str, str]] = set()
        for e in proxy.graph_edges:
            key = (e["source"], e["target"], e["edge_type"])
            if key not in seen_edges:
                seen_edges.add(key)
                trace.graph_edges.append(e)

        trace.context_snippet = context[:500]
        trace.spans.append(retrieve_span)

        # ── Generate ────────────────────────────────────────────────────
        generate_span = Span(name="generate", start_ms=_now_ms())
        messages = build_rag_messages(question, context, history)
        llm_proxy = TracingLLMProxy(self._llm)
        answer_text = llm_proxy.chat(messages, span=generate_span)
        generate_span.end_ms = _now_ms()
        trace.spans.append(generate_span)

        # Populate LLM metadata on trace
        trace.llm_request = {
            "model": llm_proxy.model_name,
            "message_count": len(messages),
            "estimated_prompt_tokens": generate_span.metadata.get(
                "estimated_prompt_tokens", 0
            ),
        }
        trace.llm_response = {
            "estimated_tokens": generate_span.metadata.get(
                "estimated_response_tokens", 0
            ),
            "latency_ms": generate_span.metadata.get("latency_ms", 0),
        }

        # Pipeline details (masking/filtering)
        if llm_proxy.pipeline_details:
            trace.pipeline = llm_proxy.pipeline_details

        # Finalize
        trace.total_ms = _now_ms() - overall_start
        sources = _extract_entity_ids(answer_text)

        result = {
            "answer": answer_text,
            "sources": sources,
            "query_pattern": intent.pattern,
            "context_snippet": context[:500],
        }
        return result, trace


def _extract_entity_ids(text: str) -> list[str]:
    """Extract entity IDs from text."""
    patterns = [
        r"VND-[\w-]+",
        r"PO-\d+",
        r"INV-\d+",
        r"CTR-\d+",
        r"MAT-[\w-]+",
        r"GR-\d+",
        r"PAY-\d+",
        r"PR-\d+",
    ]
    ids = set()
    for pattern in patterns:
        ids.update(re.findall(pattern, text))
    return sorted(ids)
