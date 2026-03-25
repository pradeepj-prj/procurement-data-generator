"""Tests for the LangGraph ReAct agent — tool building and trace structure."""

import pytest
from graphrag.config import GraphRAGConfig
from graphrag.backends.networkx_backend import NetworkXGraphBackend


@pytest.fixture(scope="module")
def backend():
    """NetworkX backend from generated CSV data."""
    config = GraphRAGConfig(
        graph_backend="networkx",
        csv_dir="output/csv",
        graph_pickle="",
    )
    return NetworkXGraphBackend(config)


class TestBuildTools:
    def test_tool_count(self, backend):
        from graphrag.llm.agent import build_tools

        tools = build_tools(backend)
        assert len(tools) == 16

    def test_tool_names(self, backend):
        from graphrag.llm.agent import build_tools

        tools = build_tools(backend)
        names = {t.name for t in tools}
        expected = {
            "get_entity",
            "get_vendor_profile",
            "get_procure_to_pay_chain",
            "get_invoice_context",
            "find_invoice_issues",
            "search_entities",
            "get_materials_for_vendor",
            "get_vendors_for_material",
            "get_vendors_for_plant_with_contracts",
            "get_graph_summary",
            "get_top_vendors_by_spend",
            "get_spend_by_category",
            "filter_purchase_orders",
            "get_invoice_aging_summary",
            "get_overdue_invoices",
            "get_high_risk_vendors",
        }
        assert names == expected

    def test_all_tools_have_descriptions(self, backend):
        from graphrag.llm.agent import build_tools

        tools = build_tools(backend)
        for tool in tools:
            assert tool.description, f"Tool {tool.name} has no description"

    def test_vendor_profile_tool_calls_backend(self, backend):
        from graphrag.llm.agent import build_tools

        tools = build_tools(backend)
        vendor_tool = next(t for t in tools if t.name == "get_vendor_profile")
        result = vendor_tool.invoke({"vendor_id": "VND-HOKUYO"})
        assert "VND-HOKUYO" in result or "Hokuyo" in result

    def test_search_tool_calls_backend(self, backend):
        from graphrag.llm.agent import build_tools

        tools = build_tools(backend)
        search_tool = next(t for t in tools if t.name == "search_entities")
        result = search_tool.invoke({"query": "Nidec"})
        assert "NIDEC" in result.upper() or "Search Results" in result

    def test_summary_tool(self, backend):
        from graphrag.llm.agent import build_tools

        tools = build_tools(backend)
        summary_tool = next(t for t in tools if t.name == "get_graph_summary")
        result = summary_tool.invoke({})
        assert "Knowledge Graph Summary" in result
        assert "Total Vertices" in result

    def test_spend_tool(self, backend):
        from graphrag.llm.agent import build_tools

        tools = build_tools(backend)
        spend_tool = next(t for t in tools if t.name == "get_top_vendors_by_spend")
        result = spend_tool.invoke({"top_n": 3})
        assert "Spend" in result


class TestAgentTraceBuilder:
    def test_creates_trace(self):
        from graphrag.llm.agent import AgentTraceBuilder

        builder = AgentTraceBuilder(question="test question")
        trace = builder.finalize("answer", ["VND-TEST"])

        assert trace.question == "test question"
        assert len(trace.spans) == 1
        assert trace.spans[0].name == "agent"
        assert trace.total_ms >= 0

    def test_adds_llm_step(self):
        from graphrag.llm.agent import AgentTraceBuilder
        from unittest.mock import MagicMock

        builder = AgentTraceBuilder(question="test")

        ai_msg = MagicMock()
        ai_msg.tool_calls = [{"name": "search_entities"}]
        ai_msg.content = "I need to search for lidar sensors."
        builder.add_llm_step(ai_msg)

        assert len(builder.agent_span.children) == 1
        span = builder.agent_span.children[0]
        assert span.name == "agent_reasoning"
        assert span.metadata["tool_calls"] == ["search_entities"]
        assert "lidar" in span.metadata["thought"]

    def test_adds_tool_step(self):
        from graphrag.llm.agent import AgentTraceBuilder
        from unittest.mock import MagicMock

        builder = AgentTraceBuilder(question="test")

        tool_msg = MagicMock()
        tool_msg.name = "get_vendor_profile"
        tool_msg.content = "## Vendor: Hokuyo\n  ID: VND-HOKUYO"
        builder.add_tool_step(tool_msg)

        assert len(builder.agent_span.children) == 1
        span = builder.agent_span.children[0]
        assert span.name == "tool:get_vendor_profile"
        assert span.metadata["tool_name"] == "get_vendor_profile"
        assert "Hokuyo" in span.metadata["result_preview"]

    def test_context_summary(self):
        from graphrag.llm.agent import AgentTraceBuilder
        from unittest.mock import MagicMock

        builder = AgentTraceBuilder(question="test")

        tool_msg = MagicMock()
        tool_msg.name = "search_entities"
        tool_msg.content = "results"
        builder.add_tool_step(tool_msg)

        tool_msg2 = MagicMock()
        tool_msg2.name = "get_vendor_profile"
        tool_msg2.content = "vendor data"
        builder.add_tool_step(tool_msg2)

        trace = builder.finalize("answer", [])
        assert "2 tool(s)" in trace.context_snippet
        assert "search_entities" in trace.context_snippet
        assert "get_vendor_profile" in trace.context_snippet

    def test_nric_masking_recorded(self):
        from graphrag.llm.agent import AgentTraceBuilder

        builder = AgentTraceBuilder(question="test S1234567D")
        builder.trace.pipeline = {
            "data_masking": {
                "original_query": "test S1234567D",
                "masked_query": "test MASKED_NRIC",
                "entities_masked": ["NRIC"],
                "client_side_masked": True,
            },
        }

        trace = builder.finalize("answer", [])
        assert trace.pipeline["data_masking"]["entities_masked"] == ["NRIC"]


class TestAgentSystemPrompt:
    def test_prompt_exists(self):
        from graphrag.llm.prompts import AGENT_SYSTEM_PROMPT

        assert "procurement" in AGENT_SYSTEM_PROMPT.lower()
        assert "tools" in AGENT_SYSTEM_PROMPT.lower()
        assert "search_entities" in AGENT_SYSTEM_PROMPT

    def test_prompt_differs_from_rag(self):
        from graphrag.llm.prompts import AGENT_SYSTEM_PROMPT, SYSTEM_PROMPT

        assert AGENT_SYSTEM_PROMPT != SYSTEM_PROMPT
        # RAG prompt says "answer based ONLY on the provided context"
        assert "ONLY on the provided context" not in AGENT_SYSTEM_PROMPT
