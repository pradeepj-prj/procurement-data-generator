"""Tests for the intent router — fallback classification (no LLM needed)."""

import pytest
from graphrag.llm.router import IntentRouter, QueryIntent


class TestFallbackClassification:
    """Test the rule-based fallback classifier (no LLM required)."""

    @pytest.fixture
    def router(self):
        """Create a router with a mock LLM that always fails, forcing fallback."""

        class MockBackend:
            pass

        class MockLLM:
            def chat(self, messages):
                return "not valid json"

        return IntentRouter(MockBackend(), MockLLM())

    def test_vendor_id_extraction(self, router):
        intent = router.classify("Tell me about VND-HOKUYO")
        assert intent.pattern == "vendor_profile"
        assert intent.entity_id == "VND-HOKUYO"

    def test_po_id_extraction(self, router):
        intent = router.classify("Show me PO-000001")
        assert intent.pattern == "p2p_chain"
        assert intent.entity_id == "PO-000001"

    def test_invoice_id_extraction(self, router):
        intent = router.classify("What's wrong with INV-000042?")
        assert intent.pattern == "invoice_context"
        assert intent.entity_id == "INV-000042"

    def test_contract_id_extraction(self, router):
        intent = router.classify("POs under CTR-00001")
        assert intent.pattern == "contract_pos"
        assert intent.entity_id == "CTR-00001"

    def test_material_id_extraction(self, router):
        intent = router.classify("Who supplies MAT-LIDAR-2D?")
        assert intent.pattern == "material_vendors"
        assert intent.entity_id == "MAT-LIDAR-2D"

    def test_invoice_issues_keyword(self, router):
        intent = router.classify("Show me invoices with problems")
        assert intent.pattern == "invoice_issues"

    def test_summary_keyword(self, router):
        intent = router.classify("Give me a summary of the data")
        assert intent.pattern == "summary"

    def test_generic_search_fallback(self, router):
        intent = router.classify("Find Nidec motors")
        assert intent.pattern == "search"
        assert intent.search_query == "Find Nidec motors"


class TestQueryIntent:
    def test_defaults(self):
        qi = QueryIntent(pattern="search")
        assert qi.entity_id is None
        assert qi.entity_type is None
        assert qi.search_query is None


class TestEntityIdExtraction:
    def test_extract_from_text(self):
        from graphrag.llm.router import _extract_entity_ids

        text = "VND-HOKUYO supplies MAT-LIDAR-2D under CTR-00001. See PO-000001 and INV-000001."
        ids = _extract_entity_ids(text)
        assert "VND-HOKUYO" in ids
        assert "MAT-LIDAR-2D" in ids
        assert "CTR-00001" in ids
        assert "PO-000001" in ids
        assert "INV-000001" in ids
