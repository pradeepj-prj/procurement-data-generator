"""Tests for the observability / tracing layer."""

import pytest
from graphrag.observability.trace import (
    QueryTrace,
    Span,
    TracingBackendProxy,
    TracingLLMProxy,
    _extract_edges_from_result,
    _extract_ids_from_result,
    _now_ms,
)


class TestSpan:
    def test_creation_and_duration(self):
        span = Span(name="test", start_ms=100.0, end_ms=150.0)
        assert span.duration_ms == 50.0

    def test_to_dict(self):
        child = Span(name="child", start_ms=110.0, end_ms=120.0, metadata={"k": "v"})
        span = Span(
            name="parent",
            start_ms=100.0,
            end_ms=200.0,
            metadata={"x": 1},
            children=[child],
        )
        d = span.to_dict()
        assert d["name"] == "parent"
        assert d["duration_ms"] == 100.0
        assert d["metadata"] == {"x": 1}
        assert len(d["children"]) == 1
        assert d["children"][0]["name"] == "child"

    def test_default_end_ms_zero(self):
        span = Span(name="open", start_ms=100.0)
        assert span.end_ms == 0.0
        assert span.duration_ms == -100.0  # not yet closed


class TestQueryTrace:
    def test_creation(self):
        trace = QueryTrace(question="test?")
        assert len(trace.trace_id) == 8
        assert trace.question == "test?"
        assert trace.total_ms == 0.0
        assert trace.graph_nodes == []
        assert trace.graph_edges == []

    def test_to_dict(self):
        trace = QueryTrace(question="test?", total_ms=42.5)
        trace.intent = {"pattern": "vendor_profile", "entity_id": "VND-TEST"}
        trace.graph_nodes = ["VND-TEST"]
        d = trace.to_dict()
        assert d["question"] == "test?"
        assert d["total_ms"] == 42.5
        assert d["intent"]["pattern"] == "vendor_profile"
        assert "VND-TEST" in d["graph_nodes"]

    def test_unique_trace_ids(self):
        ids = {QueryTrace().trace_id for _ in range(100)}
        assert len(ids) == 100


class TestEntityIdExtraction:
    def test_extract_from_dict(self):
        data = {"vendor_id": "VND-HOKUYO", "po_id": "PO-000001"}
        ids = _extract_ids_from_result(data)
        assert "VND-HOKUYO" in ids
        assert "PO-000001" in ids

    def test_extract_from_nested(self):
        data = {
            "vendor": {"vendor_id": "VND-CATL"},
            "materials": [{"material_id": "MAT-BATT-001"}],
        }
        ids = _extract_ids_from_result(data)
        assert "VND-CATL" in ids
        assert "MAT-BATT-001" in ids

    def test_extract_from_list(self):
        data = [
            {"vendor_id": "VND-A"},
            {"vendor_id": "VND-B"},
        ]
        ids = _extract_ids_from_result(data)
        assert "VND-A" in ids
        assert "VND-B" in ids

    def test_no_ids_in_empty(self):
        assert _extract_ids_from_result({}) == []
        assert _extract_ids_from_result([]) == []

    def test_non_id_keys_ignored(self):
        data = {"name": "Test Vendor", "description": "A vendor"}
        ids = _extract_ids_from_result(data)
        assert ids == []


class TestEdgeExtraction:
    def test_extract_vendor_material_edge(self):
        data = {"vendor_id": "VND-A", "material_id": "MAT-B"}
        edges = _extract_edges_from_result(data)
        assert len(edges) == 1
        assert edges[0] == {
            "source": "VND-A",
            "target": "MAT-B",
            "edge_type": "SUPPLIES",
        }  # Note: this is (vendor_id, material_id) -> wrong direction
        # Actually the edge pair is ("vendor_id", "material_id", "SUPPLIES")
        # so source=vendor, target=material

    def test_extract_po_vendor_edge(self):
        data = {"po_id": "PO-001", "vendor_id": "VND-X"}
        edges = _extract_edges_from_result(data)
        assert any(e["edge_type"] == "ORDERED_FROM" for e in edges)

    def test_extract_nested_edges(self):
        data = {
            "header": {"po_id": "PO-001", "vendor_id": "VND-X"},
            "items": [
                {"po_id": "PO-001", "material_id": "MAT-A"},
            ],
        }
        edges = _extract_edges_from_result(data)
        edge_types = {e["edge_type"] for e in edges}
        assert "ORDERED_FROM" in edge_types
        assert "CONTAINS_MATERIAL" in edge_types


class TestTracingBackendProxy:
    def test_records_span_on_call(self):
        class FakeBackend:
            def get_entity_by_id(self, entity_id):
                return {"vendor_id": entity_id, "name": "Test"}

        parent = Span(name="retrieve", start_ms=_now_ms())
        proxy = TracingBackendProxy(FakeBackend(), parent)
        result = proxy.get_entity_by_id("VND-TEST")

        assert result["name"] == "Test"
        assert len(parent.children) == 1
        assert parent.children[0].name == "retrieve.get_entity_by_id"
        assert parent.children[0].end_ms > parent.children[0].start_ms

    def test_extracts_entity_ids(self):
        class FakeBackend:
            def get_vendor_profile(self, vendor_id):
                return {
                    "vendor_id": vendor_id,
                    "materials": [{"material_id": "MAT-BATT-001"}],
                }

        parent = Span(name="retrieve", start_ms=_now_ms())
        proxy = TracingBackendProxy(FakeBackend(), parent)
        proxy.get_vendor_profile("VND-CATL")

        assert "VND-CATL" in proxy.graph_nodes
        assert "MAT-BATT-001" in proxy.graph_nodes

    def test_records_row_count_for_list(self):
        class FakeBackend:
            def get_vendor_materials(self, vendor_id):
                return [{"material_id": "MAT-A"}, {"material_id": "MAT-B"}]

        parent = Span(name="retrieve", start_ms=_now_ms())
        proxy = TracingBackendProxy(FakeBackend(), parent)
        proxy.get_vendor_materials("VND-X")

        assert parent.children[0].metadata["row_count"] == 2

    def test_non_protocol_methods_pass_through(self):
        class FakeBackend:
            custom_attr = 42

        parent = Span(name="retrieve", start_ms=_now_ms())
        proxy = TracingBackendProxy(FakeBackend(), parent)
        assert proxy.custom_attr == 42
        assert len(parent.children) == 0  # no span recorded

    def test_extracts_edges(self):
        class FakeBackend:
            def get_po_details(self, po_id):
                return {"po_id": po_id, "vendor_id": "VND-X"}

        parent = Span(name="retrieve", start_ms=_now_ms())
        proxy = TracingBackendProxy(FakeBackend(), parent)
        proxy.get_po_details("PO-001")

        assert any(e["edge_type"] == "ORDERED_FROM" for e in proxy.graph_edges)


class TestTracingLLMProxy:
    def test_records_metadata(self):
        class FakeLLM:
            model_name = "test-model"

            def chat(self, messages):
                return "This is a test response."

        span = Span(name="generate", start_ms=_now_ms())
        proxy = TracingLLMProxy(FakeLLM())
        result = proxy.chat(
            [{"role": "user", "content": "Hello world"}], span=span
        )

        assert result == "This is a test response."
        assert span.metadata["model"] == "test-model"
        assert span.metadata["message_count"] == 1
        assert span.metadata["estimated_prompt_tokens"] > 0
        assert span.metadata["estimated_response_tokens"] > 0
        assert span.metadata["latency_ms"] >= 0

    def test_no_span_still_works(self):
        class FakeLLM:
            model_name = "test-model"

            def chat(self, messages):
                return "ok"

        proxy = TracingLLMProxy(FakeLLM())
        result = proxy.chat([{"role": "user", "content": "hi"}])
        assert result == "ok"


class TestAnswerWithTrace:
    """Integration test: answer_with_trace with mock backend + mock LLM."""

    def test_produces_three_spans(self):
        class MockBackend:
            def get_vendor_profile(self, vendor_id):
                return {
                    "vendor_id": vendor_id,
                    "vendor_name": "Test Vendor",
                    "quality_score": 4.2,
                }

        class MockLLM:
            model_name = "mock-model"

            def chat(self, messages):
                # First call: classify → return JSON
                for m in messages:
                    if "classify" in m.get("content", "").lower() or "pattern" in m.get("content", "").lower():
                        return '{"pattern": "vendor_profile", "entity_id": "VND-TEST"}'
                # Second call: generate answer
                return "VND-TEST is a great vendor."

        from graphrag.llm.router import IntentRouter

        router = IntentRouter(MockBackend(), MockLLM())
        result, trace = router.answer_with_trace("Tell me about VND-TEST")

        # Verify result
        assert "VND-TEST" in result["answer"] or result["query_pattern"] is not None

        # Verify trace structure
        assert len(trace.spans) == 3
        assert trace.spans[0].name == "classify"
        assert trace.spans[1].name == "retrieve"
        assert trace.spans[2].name == "generate"

        # Verify timing
        assert trace.total_ms > 0
        for span in trace.spans:
            assert span.duration_ms >= 0

        # Verify intent captured
        assert trace.intent is not None
        assert "pattern" in trace.intent

    def test_graph_nodes_populated(self):
        class MockBackend:
            def get_vendor_profile(self, vendor_id):
                return {
                    "vendor_id": vendor_id,
                    "materials": [{"material_id": "MAT-BATT-001"}],
                    "contracts": [{"contract_id": "CTR-00001"}],
                }

        class MockLLM:
            model_name = "mock-model"

            def chat(self, messages):
                for m in messages:
                    content = m.get("content", "")
                    if "classify" in content.lower() or "pattern" in content.lower():
                        return '{"pattern": "vendor_profile", "entity_id": "VND-TEST"}'
                return "VND-TEST supplies batteries."

        from graphrag.llm.router import IntentRouter

        router = IntentRouter(MockBackend(), MockLLM())
        _, trace = router.answer_with_trace("Tell me about VND-TEST")

        assert "VND-TEST" in trace.graph_nodes
        assert "MAT-BATT-001" in trace.graph_nodes
        assert "CTR-00001" in trace.graph_nodes

    def test_trace_serializes_to_dict(self):
        class MockBackend:
            def search_entities(self, query, entity_type=None):
                return [{"vendor_id": "VND-A", "label": "Test"}]

        class MockLLM:
            model_name = "mock"

            def chat(self, messages):
                return '{"pattern": "search", "search_query": "test"}'

        from graphrag.llm.router import IntentRouter

        router = IntentRouter(MockBackend(), MockLLM())
        _, trace = router.answer_with_trace("Find test vendors")
        d = trace.to_dict()

        assert isinstance(d, dict)
        assert "trace_id" in d
        assert "spans" in d
        assert isinstance(d["spans"], list)
