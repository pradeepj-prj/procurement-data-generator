"""Tests for context formatter — works with dict data, no backend needed."""

import pytest
from graphrag.retrieval.context_formatter import (
    format_vendor_profile,
    format_p2p_chain,
    format_invoice_context,
    format_entity,
    format_search_results,
    format_list,
    format_category_tree,
    format_vendor_plant_contracts,
)


class TestFormatVendorProfile:
    def test_empty(self):
        assert "No vendor found" in format_vendor_profile({})

    def test_basic_vendor(self):
        data = {
            "id": "VND-TEST",
            "label": "Test Vendor",
            "vendor_type": "OEM",
            "country": "SG",
            "status": "ACTIVE",
            "quality_score": 85,
            "risk_score": 30,
            "on_time_delivery_rate": 92.5,
            "esg_score": 78,
            "po_count": 12,
            "materials": [
                {"id": "MAT-001", "label": "Widget A", "plant_id": "SG01", "preferred_rank": 1},
            ],
            "contracts": [
                {"id": "CTR-001", "contract_type": "QUANTITY", "status": "ACTIVE",
                 "valid_from": "2024-01-01", "valid_to": "2025-01-01"},
            ],
        }
        result = format_vendor_profile(data)
        assert "Test Vendor" in result
        assert "VND-TEST" in result
        assert "85" in result
        assert "Widget A" in result
        assert "CTR-001" in result

    def test_truncation(self):
        data = {
            "id": "VND-TEST",
            "label": "Big Vendor",
            "materials": [{"id": f"MAT-{i:03d}", "label": f"Mat {i}"} for i in range(20)],
            "contracts": [],
        }
        result = format_vendor_profile(data)
        assert "... and 10 more" in result


class TestFormatP2PChain:
    def test_empty(self):
        assert "No PO found" in format_p2p_chain({})

    def test_full_chain(self):
        data = {
            "id": "PO-000001",
            "po_date": "2024-05-01",
            "status": "FULLY_RECEIVED",
            "total_net_value": 8378.0,
            "currency": "JPY",
            "po_type": "STANDARD",
            "maverick_flag": False,
            "vendor": {"id": "VND-HOKUYO", "label": "Hokuyo", "quality_score": 82},
            "materials": [{"id": "MAT-LIDAR-2D", "label": "2D LiDAR", "quantity": 59, "unit_price": 142}],
            "contract": {"id": "CTR-00001", "contract_type": "QUANTITY"},
            "goods_receipts": [{"id": "GR-000001", "gr_date": "2024-05-11", "status": "POSTED"}],
            "invoices": [
                {
                    "id": "INV-000001",
                    "match_status": "FULL_MATCH",
                    "total_net_amount": 8378.0,
                    "payments": [{"id": "PAY-000001", "amount_applied": 8378.0}],
                },
            ],
        }
        result = format_p2p_chain(data)
        assert "PO-000001" in result
        assert "Hokuyo" in result
        assert "2D LiDAR" in result
        assert "GR-000001" in result
        assert "INV-000001" in result
        assert "PAY-000001" in result


class TestFormatInvoiceContext:
    def test_empty(self):
        assert "No invoice found" in format_invoice_context({})

    def test_with_block(self):
        data = {
            "id": "INV-000001",
            "invoice_date": "2025-07-31",
            "status": "EXCEPTION",
            "match_status": "PRICE_VARIANCE",
            "total_gross_amount": 10480.0,
            "tax_amount": 733.6,
            "total_net_amount": 11213.6,
            "payment_due_date": "2025-08-30",
            "payment_block": True,
            "block_reason": "PRICE_MISMATCH",
        }
        result = format_invoice_context(data)
        assert "PRICE_VARIANCE" in result
        assert "PRICE_MISMATCH" in result


class TestFormatEntity:
    def test_empty(self):
        assert "No entity found" in format_entity({})

    def test_basic(self):
        result = format_entity({"id": "SG01", "vertex_type": "PLANT", "label": "Singapore HQ"})
        assert "PLANT" in result
        assert "Singapore HQ" in result


class TestFormatSearchResults:
    def test_empty(self):
        assert "No results found" in format_search_results([])

    def test_basic(self):
        results = [
            {"id": "VND-001", "vertex_type": "VENDOR", "label": "Acme"},
            {"id": "MAT-001", "vertex_type": "MATERIAL", "label": "Widget"},
        ]
        text = format_search_results(results)
        assert "2 found" in text
        assert "Acme" in text


class TestFormatList:
    def test_empty(self):
        assert "no results found" in format_list([], "Results").lower()

    def test_with_items(self):
        items = [{"id": "PO-001", "vertex_type": "PURCHASE_ORDER", "label": "PO-001", "status": "ACTIVE"}]
        result = format_list(items)
        assert "PO-001" in result
        assert "ACTIVE" in result


class TestFormatCategoryTree:
    def test_empty(self):
        assert "No category found" in format_category_tree({})

    def test_with_children(self):
        data = {
            "id": "ELEC",
            "label": "Electronics",
            "level": 1,
            "children": [{"id": "ELEC-SENS", "label": "Sensors"}],
            "materials": [{"id": "MAT-001", "label": "LiDAR"}],
        }
        result = format_category_tree(data)
        assert "Electronics" in result
        assert "Sensors" in result
        assert "LiDAR" in result


class TestFormatVendorPlantContracts:
    def test_empty(self):
        assert "No vendors" in format_vendor_plant_contracts([])

    def test_with_data(self):
        data = [
            {
                "vendor": {"id": "VND-001", "label": "Acme"},
                "contracts": [
                    {"contract_id": "CTR-001", "contract_type": "QUANTITY",
                     "status": "ACTIVE", "valid_from": "2024-01-01", "valid_to": "2025-01-01"},
                ],
            },
        ]
        result = format_vendor_plant_contracts(data)
        assert "Acme" in result
        assert "CTR-001" in result
