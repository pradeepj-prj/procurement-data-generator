"""Tests for the NetworkX graph backend — no HANA Cloud needed."""

import pytest
from pathlib import Path

CSV_DIR = Path(__file__).resolve().parent.parent / "output" / "csv"
SKIP_REASON = "CSV output not found — run 'python -m procurement_generator --scale 1' first"


@pytest.fixture(scope="module")
def backend():
    """Create a NetworkX backend from generated CSV data."""
    if not (CSV_DIR / "vendor_master.csv").exists():
        pytest.skip(SKIP_REASON)

    from graphrag.config import GraphRAGConfig
    from graphrag.backends.networkx_backend import NetworkXGraphBackend

    config = GraphRAGConfig(
        graph_backend="networkx",
        csv_dir=str(CSV_DIR),
        graph_pickle="",  # disable pickle for tests
    )
    return NetworkXGraphBackend(config)


class TestGraphConstruction:
    def test_has_vertices(self, backend):
        summary = backend.get_summary()
        assert summary["total_vertices"] > 0

    def test_has_edges(self, backend):
        summary = backend.get_summary()
        assert summary["total_edges"] > 0

    def test_all_vertex_types_present(self, backend):
        summary = backend.get_summary()
        expected_types = {
            "VENDOR", "MATERIAL", "PLANT", "CATEGORY",
            "PURCHASE_ORDER", "CONTRACT", "INVOICE",
            "GOODS_RECEIPT", "PAYMENT", "PURCHASE_REQ",
        }
        assert expected_types == set(summary["vertex_counts"].keys())

    def test_all_edge_types_present(self, backend):
        summary = backend.get_summary()
        expected_types = {
            "SUPPLIES", "ORDERED_FROM", "CONTAINS_MATERIAL",
            "UNDER_CONTRACT", "INVOICED_FOR", "RECEIVED_FOR",
            "PAYS", "BELONGS_TO_CATEGORY", "CATEGORY_PARENT",
            "LOCATED_AT", "HAS_CONTRACT", "REQUESTED_MATERIAL",
            "INVOICED_BY_VENDOR", "PAID_TO_VENDOR",
        }
        assert expected_types == set(summary["edge_counts"].keys())


class TestEntityLookup:
    def test_vendor_lookup(self, backend):
        entity = backend.get_entity_by_id("VND-HOKUYO")
        assert entity
        assert entity["vertex_type"] == "VENDOR"
        assert "Hokuyo" in entity["label"]

    def test_material_lookup(self, backend):
        entity = backend.get_entity_by_id("MAT-LIDAR-2D")
        assert entity
        assert entity["vertex_type"] == "MATERIAL"

    def test_nonexistent_entity(self, backend):
        entity = backend.get_entity_by_id("DOES-NOT-EXIST")
        assert entity == {}


class TestVendorQueries:
    def test_vendor_profile(self, backend):
        profile = backend.get_vendor_profile("VND-HOKUYO")
        assert profile
        assert "materials" in profile
        assert "contracts" in profile
        assert profile["po_count"] > 0

    def test_vendor_materials(self, backend):
        materials = backend.get_vendor_materials("VND-HOKUYO")
        assert len(materials) > 0
        assert any("lidar" in m.get("label", "").lower() for m in materials)

    def test_vendor_contracts(self, backend):
        contracts = backend.get_vendor_contracts("VND-HOKUYO")
        assert len(contracts) > 0

    def test_vendor_pos(self, backend):
        pos = backend.get_vendor_pos("VND-HOKUYO")
        assert len(pos) > 0


class TestMaterialQueries:
    def test_material_vendors(self, backend):
        vendors = backend.get_material_vendors("MAT-LIDAR-2D")
        assert len(vendors) > 0
        assert any("VND-HOKUYO" == v.get("id") for v in vendors)


class TestPOQueries:
    def test_po_details(self, backend):
        po = backend.get_po_details("PO-000001")
        assert po
        assert "vendor" in po
        assert "materials" in po
        assert len(po["materials"]) > 0

    def test_p2p_chain(self, backend):
        chain = backend.get_p2p_chain("PO-000001")
        assert chain
        assert "vendor" in chain
        assert "materials" in chain
        # PO-000001 may or may not have GRs/invoices depending on data


class TestInvoiceQueries:
    def test_invoices_with_issues(self, backend):
        issues = backend.get_invoices_with_issues()
        assert len(issues) > 0
        for inv in issues:
            assert inv["match_status"] != "FULL_MATCH"

    def test_invoice_context(self, backend):
        issues = backend.get_invoices_with_issues()
        if issues:
            inv_id = issues[0]["id"]
            context = backend.get_invoice_context(inv_id)
            assert context
            assert "match_status" in context


class TestContractQueries:
    def test_contract_pos(self, backend):
        pos = backend.get_contract_pos("CTR-00001")
        assert len(pos) > 0


class TestPlantQueries:
    def test_plant_materials(self, backend):
        materials = backend.get_plant_materials("SG01")
        assert len(materials) > 0

    def test_vendor_plant_contracts(self, backend):
        results = backend.get_vendor_plant_contracts("SG01")
        assert len(results) > 0
        for entry in results:
            assert "vendor" in entry
            assert "contracts" in entry
            assert len(entry["contracts"]) > 0


class TestCategoryQueries:
    def test_category_tree(self, backend):
        tree = backend.get_category_tree("ELEC")
        assert tree
        assert "children" in tree
        assert len(tree["children"]) > 0
        assert "materials" in tree


class TestSearch:
    def test_search_by_name(self, backend):
        results = backend.search_entities("Nidec")
        assert len(results) > 0

    def test_search_with_type_filter(self, backend):
        results = backend.search_entities("LiDAR", "MATERIAL")
        assert len(results) > 0
        for r in results:
            assert r["vertex_type"] == "MATERIAL"

    def test_search_no_results(self, backend):
        results = backend.search_entities("xyznonexistent12345")
        assert len(results) == 0
