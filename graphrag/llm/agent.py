"""LangGraph ReAct agent for multi-step procurement reasoning.

Uses LangGraph's `create_react_agent` with LangChain tool definitions.
GenAI Hub is used only as the LLM transport via `ChatOpenAI` proxy.

Requires: pip install -e ".[graphrag-agent]"
"""

from __future__ import annotations

from typing import Any, Generator

from graphrag.backends.protocol import GraphBackend
from graphrag.config import GraphRAGConfig
from graphrag.llm.genai_hub import GenAIHubClient, mask_nric
from graphrag.llm.prompts import AGENT_SYSTEM_PROMPT
from graphrag.observability.trace import (
    QueryTrace,
    Span,
    _extract_ids_from_result,
    _now_ms,
)
from graphrag.retrieval import context_formatter as fmt


def build_tools(backend: GraphBackend) -> list:
    """Create 16 LangChain @tool functions wrapping backend methods."""
    from langchain_core.tools import tool

    @tool
    def get_entity(entity_id: str) -> str:
        """Look up any entity by ID (vendor, material, PO, contract, invoice, GR, payment, PR, plant, category)."""
        data = backend.get_entity_by_id(entity_id)
        return fmt.format_entity(data)

    @tool
    def get_vendor_profile(vendor_id: str) -> str:
        """Get a complete vendor dossier — performance scores, materials supplied, contracts, and PO count."""
        data = backend.get_vendor_profile(vendor_id)
        return fmt.format_vendor_profile(data)

    @tool
    def get_procure_to_pay_chain(po_id: str) -> str:
        """Get the full procure-to-pay chain for a PO: vendor, materials, goods receipts, invoices, and payments."""
        data = backend.get_p2p_chain(po_id)
        return fmt.format_p2p_chain(data)

    @tool
    def get_invoice_context(invoice_id: str) -> str:
        """Get three-way match context for an invoice — linked PO, goods receipts, vendor, and payments."""
        data = backend.get_invoice_context(invoice_id)
        return fmt.format_invoice_context(data)

    @tool
    def find_invoice_issues() -> str:
        """Find all invoices with match problems (match_status != FULL_MATCH)."""
        items = backend.get_invoices_with_issues()
        return fmt.format_list(items, "Invoices with Issues")

    @tool
    def search_entities(query: str, entity_type: str | None = None) -> str:
        """Search for entities by name or description. Optional entity_type filter (VENDOR, MATERIAL, PURCHASE_ORDER, CONTRACT, INVOICE, GOODS_RECEIPT, PAYMENT, PURCHASE_REQ, PLANT, CATEGORY)."""
        items = backend.search_entities(query, entity_type)
        return fmt.format_search_results(items)

    @tool
    def get_materials_for_vendor(vendor_id: str) -> str:
        """Get all materials a vendor supplies, with plant and ranking info."""
        items = backend.get_vendor_materials(vendor_id)
        return fmt.format_list(items, "Vendor Materials")

    @tool
    def get_vendors_for_material(material_id: str) -> str:
        """Get all vendors supplying a specific material."""
        items = backend.get_material_vendors(material_id)
        return fmt.format_list(items, "Material Vendors")

    @tool
    def get_vendors_for_plant_with_contracts(plant_id: str) -> str:
        """Multi-hop query: find all vendors supplying materials at a plant, along with their contracts."""
        items = backend.get_vendor_plant_contracts(plant_id)
        return fmt.format_vendor_plant_contracts(items)

    @tool
    def get_graph_summary() -> str:
        """Get an overview of the knowledge graph — vertex and edge counts by type."""
        data = backend.get_summary()
        lines = [
            "## Knowledge Graph Summary",
            f"  Total Vertices: {data.get('total_vertices', 0)}",
            f"  Total Edges: {data.get('total_edges', 0)}",
            "",
            "### Vertex Counts",
        ]
        for vtype, count in sorted(data.get("vertex_counts", {}).items()):
            lines.append(f"  {vtype}: {count}")
        lines.append("\n### Edge Counts")
        for etype, count in sorted(data.get("edge_counts", {}).items()):
            lines.append(f"  {etype}: {count}")
        return "\n".join(lines)

    @tool
    def get_top_vendors_by_spend(top_n: int = 10) -> str:
        """Get the top vendors ranked by total PO spend."""
        items = backend.get_spend_by_vendor(top_n)
        return fmt.format_spend_table(items, "Top Vendors by Spend")

    @tool
    def get_spend_by_category(top_n: int = 10) -> str:
        """Get spend breakdown aggregated by material category."""
        items = backend.get_spend_by_category(top_n)
        return fmt.format_spend_table(items, "Spend by Category")

    @tool
    def filter_purchase_orders(
        status: str | None = None,
        maverick_only: bool = False,
        min_value: float | None = None,
        max_value: float | None = None,
    ) -> str:
        """Filter purchase orders by status, maverick flag, and/or value range."""
        items = backend.get_pos_by_filter(
            status=status,
            maverick=True if maverick_only else None,
            min_value=min_value,
            max_value=max_value,
        )
        return fmt.format_po_list(items)

    @tool
    def get_invoice_aging_summary() -> str:
        """Get invoice aging summary — counts and totals grouped by match status."""
        items = backend.get_invoice_aging()
        return fmt.format_invoice_aging(items)

    @tool
    def get_overdue_invoices() -> str:
        """Get invoices that are past their payment due date and not yet paid."""
        items = backend.get_overdue_invoices()
        return fmt.format_po_list(items)

    @tool
    def get_high_risk_vendors(risk_threshold: float = 3.0) -> str:
        """Get vendors with risk scores above a threshold, with quality and delivery metrics."""
        items = backend.get_vendor_risk_summary(risk_threshold)
        return fmt.format_vendor_risk(items)

    return [
        get_entity,
        get_vendor_profile,
        get_procure_to_pay_chain,
        get_invoice_context,
        find_invoice_issues,
        search_entities,
        get_materials_for_vendor,
        get_vendors_for_material,
        get_vendors_for_plant_with_contracts,
        get_graph_summary,
        get_top_vendors_by_spend,
        get_spend_by_category,
        filter_purchase_orders,
        get_invoice_aging_summary,
        get_overdue_invoices,
        get_high_risk_vendors,
    ]


def create_procurement_agent(backend: GraphBackend, config: GraphRAGConfig) -> Any:
    """Create a LangGraph ReAct agent with procurement tools.

    Uses GenAI Hub only as the LLM transport via ChatOpenAI proxy.
    LangGraph handles the ReAct loop and tool execution natively.
    """
    from langgraph.prebuilt import create_react_agent

    # Configure AICORE env vars so the proxy can authenticate
    GenAIHubClient._configure_env(config)

    # Use ChatOpenAI from GenAI Hub's LangChain proxy — GenAI Hub is just
    # the transport layer, LangChain/LangGraph handle everything else
    from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
    from gen_ai_hub.proxy.langchain.openai import ChatOpenAI

    proxy = get_proxy_client("gen-ai-hub")
    llm = ChatOpenAI(proxy_model_name=config.agent_model_name, proxy_client=proxy)

    tools = build_tools(backend)

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=AGENT_SYSTEM_PROMPT,
    )
    return agent


class AgentTraceBuilder:
    """Builds a QueryTrace from LangGraph agent execution steps."""

    # Maps tool_name → (arg_key_for_anchor, edge_type, anchor_is_source)
    _TOOL_EDGE_MAP: dict[str, tuple[str, str, bool]] = {
        "get_vendors_for_material": ("material_id", "SUPPLIES", False),  # VND → MAT
        "get_materials_for_vendor": ("vendor_id", "SUPPLIES", True),  # VND → MAT
        "get_procure_to_pay_chain": ("po_id", "ORDERED_FROM", False),  # PO → VND
        "get_invoice_context": ("invoice_id", "INVOICED_FOR", True),  # INV → PO
        "get_vendors_for_plant_with_contracts": ("plant_id", "LOCATED_AT", False),
    }

    def __init__(self, question: str) -> None:
        self.trace = QueryTrace(question=question)
        self.agent_span = Span(name="agent", start_ms=_now_ms())
        self._all_tool_results: list[str] = []
        self._pending_tool_calls: dict[str, dict] = {}  # tool_call_id → {name, args}
        self._tool_invocations: list[tuple[str, dict, str]] = []  # (name, args, result)
        self._step_start: float = _now_ms()

    def add_llm_step(self, ai_message: Any) -> None:
        """Record an LLM reasoning step."""
        now = _now_ms()
        span = Span(
            name="agent_reasoning",
            start_ms=self._step_start,
            end_ms=now,
        )

        tool_calls = getattr(ai_message, "tool_calls", [])
        content = getattr(ai_message, "content", "")

        # Store pending tool calls so we can pair args with results
        for tc in tool_calls:
            tc_id = tc.get("id", "")
            if tc_id:
                self._pending_tool_calls[tc_id] = {
                    "name": tc.get("name", "?"),
                    "args": tc.get("args", {}),
                }

        span.metadata = {
            "tool_calls": [tc.get("name", "?") for tc in tool_calls] if tool_calls else [],
            "is_final": len(tool_calls) == 0,
        }
        if content and isinstance(content, str):
            span.metadata["thought"] = content[:500]

        self.agent_span.children.append(span)
        self._step_start = now

    def add_tool_step(self, tool_message: Any) -> None:
        """Record a tool execution step."""
        now = _now_ms()
        tool_name = getattr(tool_message, "name", "unknown")
        content = getattr(tool_message, "content", "")
        tool_call_id = getattr(tool_message, "tool_call_id", "")

        # Pair with pending tool call args
        args = {}
        if tool_call_id and tool_call_id in self._pending_tool_calls:
            args = self._pending_tool_calls.pop(tool_call_id).get("args", {})

        span = Span(
            name=f"tool:{tool_name}",
            start_ms=self._step_start,
            end_ms=now,
            metadata={
                "tool_name": tool_name,
                "result_preview": content[:300] if isinstance(content, str) else "",
            },
        )

        self.agent_span.children.append(span)
        if isinstance(content, str):
            self._all_tool_results.append(content)
            self._tool_invocations.append((tool_name, args, content))
        self._step_start = now

    def finalize(self, answer: str, sources: list[str]) -> QueryTrace:
        """Complete the trace with final answer and extracted graph data."""
        self.agent_span.end_ms = _now_ms()
        self.trace.spans = [self.agent_span]
        self.trace.total_ms = self.agent_span.duration_ms
        self.trace.intent = {"mode": "agent"}

        # Extract entity IDs from all tool results
        all_ids: set[str] = set()
        for result_text in self._all_tool_results:
            ids = _extract_ids_from_result({"text": result_text})
            all_ids.update(ids)

        self.trace.graph_nodes = sorted(all_ids)
        self.trace.graph_edges = self._infer_edges(all_ids)
        self.trace.context_snippet = self._context_summary()

        return self.trace

    def _infer_edges(self, all_node_ids: set[str]) -> list[dict[str, str]]:
        """Infer graph edges from tool invocations.

        Uses the tool name + args to determine the anchor entity, then
        extracts entity IDs from the result text as the other end of edges.
        """
        seen: set[str] = set()
        edges: list[dict[str, str]] = []

        for tool_name, args, result_text in self._tool_invocations:
            result_ids = set(_extract_ids_from_result({"text": result_text}))

            # Strategy 1: tool-specific edge mapping
            if tool_name in self._TOOL_EDGE_MAP:
                arg_key, edge_type, anchor_is_source = self._TOOL_EDGE_MAP[tool_name]
                anchor_id = args.get(arg_key, "")
                if anchor_id and anchor_id in all_node_ids:
                    for rid in result_ids:
                        if rid != anchor_id and rid in all_node_ids:
                            if anchor_is_source:
                                key = f"{anchor_id}-{edge_type}-{rid}"
                                edge = {"source": anchor_id, "target": rid, "edge_type": edge_type}
                            else:
                                key = f"{rid}-{edge_type}-{anchor_id}"
                                edge = {"source": rid, "target": anchor_id, "edge_type": edge_type}
                            if key not in seen:
                                seen.add(key)
                                edges.append(edge)
                continue

            # Strategy 2: vendor_profile — vendor connects to materials and contracts
            if tool_name == "get_vendor_profile":
                anchor_id = args.get("vendor_id", "")
                if anchor_id and anchor_id in all_node_ids:
                    for rid in result_ids:
                        if rid == anchor_id:
                            continue
                        if rid.startswith("MAT-"):
                            et = "SUPPLIES"
                        elif rid.startswith("CTR-"):
                            et = "HAS_CONTRACT"
                        elif rid.startswith("PO-"):
                            et = "ORDERED_FROM"
                        else:
                            continue
                        key = f"{anchor_id}-{et}-{rid}"
                        if key not in seen:
                            seen.add(key)
                            edges.append({"source": anchor_id, "target": rid, "edge_type": et})

        return edges

    def _context_summary(self) -> str:
        """Summarize tools called for the context snippet."""
        tool_spans = [
            s for s in self.agent_span.children if s.name.startswith("tool:")
        ]
        if not tool_spans:
            return "No tools called."
        lines = [f"Agent called {len(tool_spans)} tool(s):"]
        for s in tool_spans:
            lines.append(f"  - {s.metadata.get('tool_name', '?')}")
        return "\n".join(lines)


def run_agent_with_trace(
    agent: Any, question: str, history: list[dict] | None = None
) -> tuple[dict, QueryTrace]:
    """Invoke the ReAct agent and capture a structured trace."""
    from langchain_core.messages import AIMessage, HumanMessage

    # Client-side NRIC masking
    masked_question, nric_entities = mask_nric(question)

    trace_builder = AgentTraceBuilder(question=question)
    if nric_entities:
        trace_builder.trace.pipeline = {
            "data_masking": {
                "original_query": question,
                "masked_query": masked_question,
                "entities_masked": nric_entities,
                "client_side_masked": True,
            },
        }

    # Build input messages
    messages = []
    if history:
        messages.extend(
            AIMessage(content=m["content"]) if m["role"] == "assistant"
            else HumanMessage(content=m["content"])
            for m in history
        )
    messages.append(HumanMessage(content=masked_question))

    # Stream agent steps for per-step timing
    final_answer = ""
    from graphrag.llm.router import _extract_entity_ids

    for step in agent.stream({"messages": messages}, stream_mode="updates"):
        if "agent" in step:
            ai_msg = step["agent"]["messages"][-1]
            trace_builder.add_llm_step(ai_msg)
            tool_calls = getattr(ai_msg, "tool_calls", [])
            if not tool_calls:
                final_answer = getattr(ai_msg, "content", "")
        elif "tools" in step:
            for tool_msg in step["tools"]["messages"]:
                trace_builder.add_tool_step(tool_msg)

    sources = _extract_entity_ids(final_answer)
    trace = trace_builder.finalize(final_answer, sources)

    return {
        "answer": final_answer,
        "sources": sources,
        "query_pattern": "agent",
        "context_snippet": trace.context_snippet,
    }, trace


def stream_agent_steps(
    agent: Any, question: str, history: list[dict] | None = None
) -> Generator[dict, None, None]:
    """Stream agent execution as structured step events.

    Yields dicts with an ``event`` key:
      - ``step``  — intermediate reasoning or tool result
      - ``answer`` — final response with full trace
      - ``error``  — if agent execution fails
    """
    from langchain_core.messages import AIMessage, HumanMessage

    from graphrag.llm.router import _extract_entity_ids

    try:
        masked_question, nric_entities = mask_nric(question)

        trace_builder = AgentTraceBuilder(question=question)
        if nric_entities:
            trace_builder.trace.pipeline = {
                "data_masking": {
                    "original_query": question,
                    "masked_query": masked_question,
                    "entities_masked": nric_entities,
                    "client_side_masked": True,
                },
            }

        messages: list[Any] = []
        if history:
            messages.extend(
                AIMessage(content=m["content"]) if m["role"] == "assistant"
                else HumanMessage(content=m["content"])
                for m in history
            )
        messages.append(HumanMessage(content=masked_question))

        final_answer = ""
        step_index = 0

        for step in agent.stream({"messages": messages}, stream_mode="updates"):
            if "agent" in step:
                ai_msg = step["agent"]["messages"][-1]
                trace_builder.add_llm_step(ai_msg)

                tool_calls = getattr(ai_msg, "tool_calls", [])
                thought = getattr(ai_msg, "content", "") or ""

                yield {
                    "event": "step",
                    "type": "reasoning",
                    "thought": thought[:200] if isinstance(thought, str) else "",
                    "tool_calls": [tc.get("name", "?") for tc in tool_calls] if tool_calls else [],
                    "step_index": step_index,
                }
                step_index += 1

                if not tool_calls:
                    final_answer = thought

            elif "tools" in step:
                for tool_msg in step["tools"]["messages"]:
                    trace_builder.add_tool_step(tool_msg)
                    tool_name = getattr(tool_msg, "name", "unknown")
                    content = getattr(tool_msg, "content", "")

                    yield {
                        "event": "step",
                        "type": "tool_result",
                        "tool_name": tool_name,
                        "result_preview": content[:200] if isinstance(content, str) else "",
                        "step_index": step_index,
                    }
                    step_index += 1

        sources = _extract_entity_ids(final_answer)
        trace = trace_builder.finalize(final_answer, sources)

        yield {
            "event": "answer",
            "answer": final_answer,
            "sources": sources,
            "query_pattern": "agent",
            "context_snippet": trace.context_snippet,
            "trace": trace.to_dict(),
        }

    except Exception as exc:
        yield {"event": "error", "message": str(exc)}
