"""Tests for relational query methods on the NetworkX backend."""

import pytest
from graphrag.backends.networkx_backend import NetworkXGraphBackend
from graphrag.config import GraphRAGConfig


@pytest.fixture(scope="module")
def backend():
    """Create a NetworkX backend from the generated CSV data."""
    config = GraphRAGConfig(
        graph_backend="networkx",
        csv_dir="output/csv",
        graph_pickle="",  # force rebuild from CSV
    )
    return NetworkXGraphBackend(config)


class TestSpendByVendor:
    def test_returns_results(self, backend):
        items = backend.get_spend_by_vendor()
        assert len(items) > 0
        for item in items:
            assert "vendor_id" in item
            assert "total_spend" in item
            assert "po_count" in item

    def test_respects_top_n(self, backend):
        items = backend.get_spend_by_vendor(top_n=3)
        assert len(items) == 3

    def test_sorted_descending(self, backend):
        items = backend.get_spend_by_vendor(top_n=5)
        spends = [item["total_spend"] for item in items]
        assert spends == sorted(spends, reverse=True)


class TestSpendByCategory:
    def test_returns_results(self, backend):
        items = backend.get_spend_by_category()
        assert len(items) > 0
        for item in items:
            assert "category_id" in item
            assert "total_spend" in item

    def test_sorted_descending(self, backend):
        items = backend.get_spend_by_category()
        spends = [item["total_spend"] for item in items]
        assert spends == sorted(spends, reverse=True)


class TestPosByFilter:
    def test_no_filter_returns_pos(self, backend):
        items = backend.get_pos_by_filter()
        assert len(items) > 0

    def test_maverick_only(self, backend):
        items = backend.get_pos_by_filter(maverick=True)
        for item in items:
            assert item["maverick_flag"] is True

    def test_min_value(self, backend):
        items = backend.get_pos_by_filter(min_value=10000)
        for item in items:
            assert item["total_net_value"] >= 10000

    def test_limit(self, backend):
        items = backend.get_pos_by_filter(limit=5)
        assert len(items) <= 5


class TestInvoiceAging:
    def test_returns_results(self, backend):
        items = backend.get_invoice_aging()
        assert len(items) > 0
        for item in items:
            assert "match_status" in item
            assert "count" in item
            assert "total_amount" in item

    def test_full_match_present(self, backend):
        items = backend.get_invoice_aging()
        statuses = {item["match_status"] for item in items}
        assert "FULL_MATCH" in statuses


class TestOverdueInvoices:
    def test_returns_list(self, backend):
        # May be empty if all invoices are paid or not yet due
        items = backend.get_overdue_invoices()
        assert isinstance(items, list)


class TestVendorRiskSummary:
    def test_returns_results(self, backend):
        # Use a low threshold to ensure results
        items = backend.get_vendor_risk_summary(threshold=1.0)
        assert len(items) > 0

    def test_respects_threshold(self, backend):
        threshold = 3.0
        items = backend.get_vendor_risk_summary(threshold=threshold)
        for item in items:
            assert item["risk_score"] > threshold

    def test_sorted_descending(self, backend):
        items = backend.get_vendor_risk_summary(threshold=1.0)
        if len(items) > 1:
            scores = [item["risk_score"] for item in items]
            assert scores == sorted(scores, reverse=True)
