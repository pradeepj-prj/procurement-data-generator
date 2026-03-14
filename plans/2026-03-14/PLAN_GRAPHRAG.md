# Plan: Python GraphRAG Module (HANA Cloud Graph Engine Alternative)

## Context

HANA Cloud's Property Graph Engine is included in the base HANA Cloud subscription but requires a **3+ vCPU / 45 GB instance** — not available on trial/free tier. The `--no-graph` fallback (vertex/edge SQL views only) works without the graph engine, but offers no traversal algorithms.

This plan builds a **Python-based graph module** that loads the same 10-vertex / 14-edge schema from CSV, provides traversal and context retrieval, and exposes it via an MCP server for SAP GenAI Hub consumption. Works entirely outside HANA Cloud.

## Approach: NetworkX + MCP Server

**Why NetworkX over Neo4j:** The dataset is small (~10K rows at 1x, ~106K at 10x) — fits easily in memory. No operational overhead. NetworkX gives us traversal, shortest path, BFS, and subgraph extraction out of the box. Neo4j can be added later if needed.

**Why MCP:** SAP GenAI Hub supports MCP for tool-augmented agents. An MCP server lets any LLM agent (GenAI Hub, Claude, etc.) query the procurement graph via structured tool calls.

---

## New Files

| File | Purpose |
|------|---------|
| `scripts/graph/graph_builder.py` | Build NetworkX DiGraph from CSV data (10 vertex types, 14 edge types) |
| `scripts/graph/graph_rag.py` | Context retrieval: subgraph extraction, neighbor lookup, path finding, context formatting |
| `scripts/graph/mcp_server.py` | MCP server exposing graph queries as tools for GenAI Hub / any LLM agent |
| `scripts/graph/README.md` | Setup, usage, architecture, example queries |

## Modified Files

| File | Change |
|------|--------|
| `pyproject.toml` | Add `[project.optional-dependencies] graph = ["networkx>=3.0", "mcp>=1.0"]` |
| `CLAUDE.md` | Add graph module commands |
| `NEXT_STEPS.md` | Update graph section with Python alternative |

---

## Part 1: Graph Builder (`scripts/graph/graph_builder.py`)

Loads 29 CSVs, builds a NetworkX DiGraph matching the HANA SQL schema exactly.

### Reuse
- `ml/common/db_config.py` → `load_table_csv()` for CSV loading + type coercion
- `scripts/graph/create_graph_workspace.sql` → vertex/edge definitions (replicate in Python)

### Vertices (10 types)
Each node ID = the entity PK (already unique across types via prefixes: VND-, MAT-, PO-, CTR-, INV-, GR-, PAY-, PR-, plant codes, category codes). Node attributes:
- `vertex_type`: string label (VENDOR, MATERIAL, etc.)
- `label`: human-readable name (vendor_name, description, or entity ID)
- Type-specific properties: same columns as the HANA vertex views (quality_score, risk_score, etc.)

### Edges (14 types)
Each edge stored as a directed edge with `edge_type` attribute + relationship properties. Source tables:
- `source_list` → SUPPLIES (vendor → material)
- `po_header` → ORDERED_FROM (PO → vendor), LOCATED_AT (PO → plant)
- `po_line_item` → CONTAINS_MATERIAL (PO → material), UNDER_CONTRACT (PO → contract, where contract_id not null)
- `invoice_header` → INVOICED_FOR (invoice → PO), INVOICED_BY_VENDOR (invoice → vendor)
- `gr_header` → RECEIVED_FOR (GR → PO)
- `payment_invoice_link` → PAYS (payment → invoice)
- `payment` → PAID_TO_VENDOR (payment → vendor)
- `material_master` → BELONGS_TO_CATEGORY (material → category)
- `category_hierarchy` → CATEGORY_PARENT (category → parent, where parent not null)
- `contract_header` → HAS_CONTRACT (vendor → contract)
- `pr_line_item` → REQUESTED_MATERIAL (PR → material)

### API
```python
class ProcurementGraph:
    def __init__(self, csv_dir: str = "output/csv"):
        self.graph: nx.DiGraph
        self.vertices_by_type: dict[str, list[str]]  # type → [node_ids]

    def build(self) -> None:  # load CSVs, populate graph
    def save(self, path: str) -> None:  # pickle for fast reload
    @classmethod
    def load(cls, path: str) -> "ProcurementGraph":  # load from pickle

    # Accessors
    def get_node(self, node_id: str) -> dict  # node attributes
    def get_neighbors(self, node_id: str, edge_type: str = None, direction: str = "both") -> list[dict]
    def get_subgraph(self, node_id: str, hops: int = 2) -> nx.DiGraph  # ego graph
    def get_path(self, source: str, target: str) -> list[str]  # shortest path
    def get_nodes_by_type(self, vertex_type: str) -> list[dict]

    # Stats
    def summary(self) -> dict  # vertex/edge counts by type
```

---

## Part 2: Graph RAG Context Retriever (`scripts/graph/graph_rag.py`)

Extracts graph context and formats it as structured text for LLM consumption.

### Key Functions
```python
def get_entity_context(graph: ProcurementGraph, entity_id: str, hops: int = 2) -> str:
    """Full context for an entity: attributes + neighbors + paths."""

def get_procurement_chain(graph: ProcurementGraph, entity_id: str) -> str:
    """Follow the procure-to-pay chain: PR → PO → GR → Invoice → Payment."""

def get_vendor_profile(graph: ProcurementGraph, vendor_id: str) -> str:
    """Vendor context: contracts, materials supplied, POs, invoices, payments."""

def get_invoice_context(graph: ProcurementGraph, invoice_id: str) -> str:
    """Invoice three-way match context: PO, GR, vendor, contract, payment."""

def search_entities(graph: ProcurementGraph, query: str, vertex_type: str = None) -> list[dict]:
    """Simple text search over node labels and attributes."""

def format_subgraph_as_text(subgraph: nx.DiGraph) -> str:
    """Format a subgraph as structured text for LLM context window."""
```

Context output format (structured text, not JSON — better for LLM comprehension):
```
=== Vendor: VND-SG-00001 (Precision Robotics Pte Ltd) ===
Type: OEM | Country: SG | Status: ACTIVE
Quality: 92 | Risk: 15 | On-time: 97.5%

-- Supplies 5 materials --
  MAT-00001 (Servo Motor Assembly) via Plant 1000 [rank 1, APPROVED]
  MAT-00015 (Controller Board) via Plant 1000 [rank 2, APPROVED]
  ...

-- 3 Active Contracts --
  CTR-00001: QUANTITY contract, valid 2025-01-15 to 2026-01-14, ACTIVE
  ...

-- 12 Purchase Orders (last 6 months) --
  PO-00001: 2025-06-15, $45,230.00, FULLY_RECEIVED, maverick=false
  ...
```

---

## Part 3: MCP Server (`scripts/graph/mcp_server.py`)

Exposes graph queries as MCP tools. Any MCP-compatible agent (SAP GenAI Hub via MCP Gateway, Claude, etc.) can call these.

### Tools
| Tool Name | Description | Parameters |
|-----------|-------------|------------|
| `get_entity` | Get attributes and immediate relationships for any entity | `entity_id: str` |
| `get_procurement_chain` | Trace the full procure-to-pay flow for a PO, invoice, or GR | `entity_id: str` |
| `get_vendor_profile` | Complete vendor dossier: contracts, materials, POs, quality | `vendor_id: str` |
| `get_invoice_context` | Three-way match context for an invoice | `invoice_id: str` |
| `search_entities` | Find entities by name or attribute | `query: str, type: str (optional)` |
| `get_graph_stats` | Vertex/edge counts by type | *(none)* |

### Implementation
- Use `mcp` Python SDK (`from mcp.server import Server`)
- Load graph on startup (from pickle or rebuild from CSV)
- Stateless tools — each call queries the in-memory graph
- Run via `python scripts/graph/mcp_server.py --csv-dir output/csv`

---

## Part 4: Dependencies & Docs

### `pyproject.toml`
Add optional dependency group:
```toml
[project.optional-dependencies]
graph = ["networkx>=3.0", "mcp>=1.0"]
```

### `CLAUDE.md`
Add commands:
```bash
# Install graph dependencies
pip install -e ".[graph]"

# Build graph from CSV
python -c "from scripts.graph.graph_builder import ProcurementGraph; g = ProcurementGraph(); g.build(); g.save('output/graph.pkl')"

# Run MCP server
python scripts/graph/mcp_server.py --csv-dir output/csv

# Run MCP server (from saved graph)
python scripts/graph/mcp_server.py --graph output/graph.pkl
```

### `scripts/graph/README.md`
- Explain HANA Cloud entitlement situation (3+ vCPU required for GRAPH WORKSPACE)
- Three deployment options: (1) HANA GRAPH WORKSPACE, (2) HANA SQL views only (`--no-graph`), (3) Python NetworkX + MCP
- Architecture diagram: CSV → NetworkX → MCP Server → GenAI Hub Agent
- Example queries and expected output
- How to connect to SAP GenAI Hub via MCP Gateway

---

## Verification

```bash
# Install
pip install -e ".[graph]"

# Build graph and print summary (vertex/edge counts by type)
python -c "
from scripts.graph.graph_builder import ProcurementGraph
g = ProcurementGraph('output/csv')
g.build()
print(g.summary())
g.save('output/graph.pkl')
"

# Test context retrieval
python -c "
from scripts.graph.graph_builder import ProcurementGraph
from scripts.graph.graph_rag import get_vendor_profile
g = ProcurementGraph.load('output/graph.pkl')
print(get_vendor_profile(g, 'VND-SG-00001'))
"

# Run MCP server
python scripts/graph/mcp_server.py --csv-dir output/csv
```
