"""Intent router — classifies questions and routes to the right graph query."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from graphrag.backends.protocol import GraphBackend
from graphrag.llm.genai_hub import GenAIHubClient
from graphrag.llm.prompts import build_rag_messages, build_router_messages
from graphrag.retrieval import context_formatter as fmt


@dataclass
class QueryIntent:
    """Classified intent with pattern name and extracted IDs."""

    pattern: str
    entity_id: str | None = None
    entity_type: str | None = None
    search_query: str | None = None


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
        if "summary" in q or "overview" in q:
            return QueryIntent(pattern="summary")

        return QueryIntent(pattern="search", search_query=question)

    def retrieve(self, intent: QueryIntent) -> str:
        """Execute the graph query for a classified intent and format results."""
        b = self._backend
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
