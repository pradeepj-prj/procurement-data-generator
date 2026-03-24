# Plan: CF Deployment, UI, Observability & Relational MCP Tools

**Date:** 2026-03-24
**Status:** Ready for implementation

## Overview

Four workstreams to take the GraphRAG system from a working backend to a demo-ready application:

1. **Observability Layer** — Structured tracing of the full question-to-answer pipeline
2. **Relational MCP Tools** — Direct SQL query tools beyond graph traversals
3. **UI** — React app with graph visualization, showing nodes/edges/traversal paths and observability data
4. **CF Deployment** — Deploy REST API + UI to Cloud Foundry on BTP

Implementation order matters: observability first (cross-cutting, feeds the UI), then relational tools (quick, extends MCP), then UI (consumes both), then CF (packages everything).

---

## Phase 1: Observability Layer

### Goal

Capture structured traces for every query: intent classification, tool/backend calls, graph nodes traversed, LLM prompts/responses/tokens/latency. Expose via API so the UI can render the "how it got there" view.

### Design

A lightweight `TraceContext` that accumulates spans as the query flows through the pipeline. No external dependencies (no OpenTelemetry/Jaeger) — just a Python dataclass that serializes to JSON and gets returned alongside the answer.

### 1a. Trace data model

**New file:** `graphrag/observability/trace.py`

```python
@dataclass
class Span:
    name: str               # e.g. "classify", "retrieve.get_vendor_profile", "llm.chat"
    start_ms: float
    end_ms: float
    metadata: dict           # tool-specific: {pattern, entity_id, sql, row_count, tokens, model, ...}
    children: list[Span]     # nested spans (e.g. retrieve → multiple backend calls)

@dataclass
class QueryTrace:
    trace_id: str            # uuid
    question: str
    total_ms: float
    intent: dict             # {pattern, entity_id, entity_type, search_query, confidence}
    graph_nodes: list[str]   # all entity IDs touched during retrieval
    graph_edges: list[dict]  # [{source, target, edge_type}] — edges traversed
    spans: list[Span]        # top-level spans: [classify, retrieve, generate]
    context_snippet: str     # first 500 chars of retrieved context
    llm_request: dict        # {model, message_count, prompt_tokens (est)}
    llm_response: dict       # {tokens (est), finish_reason}
```

### 1b. Instrument the router

**Modified file:** `graphrag/llm/router.py`

- `classify()` → wrap in span, record pattern + entity_id + latency
- `retrieve()` → wrap in span, collect entity IDs from backend results
- `answer()` → wrap full pipeline, return `QueryTrace` alongside response
- New method: `answer_with_trace(question, history) → (dict, QueryTrace)`

### 1c. Instrument the backends

**Modified files:** `graphrag/backends/hana_backend.py`, `graphrag/backends/networkx_backend.py`

- Wrap each protocol method to emit a child span with:
  - Method name, parameters, result count, latency
  - For HANA: SQL query text (sanitized — no param values)
  - Entity IDs present in results → accumulate into `graph_nodes`
  - Edge relationships from results → accumulate into `graph_edges`

Approach: a decorator or context manager that the router passes down, so backends don't need to know about tracing unless a trace context is active.

### 1d. Instrument the LLM client

**Modified file:** `graphrag/llm/genai_hub.py`

- Wrap `chat()` and `chat_stream()` to record:
  - Model name, message count, estimated prompt tokens (char count / 4)
  - Response time, estimated output tokens
  - No raw prompt/response content in trace (too large) — just metadata

### 1e. Expose traces via API

**Modified file:** `graphrag/api.py`

- Add `include_trace: bool = False` field to `ChatRequest`
- New response model `ChatResponseWithTrace` that extends `ChatResponse` with a `trace: QueryTrace` field
- When `include_trace=True`, call `router.answer_with_trace()` and return full trace
- New endpoint `GET /traces/{trace_id}` — optional, stores last N traces in memory (LRU)

### Files changed (Phase 1)

| File | Change |
|------|--------|
| `graphrag/observability/__init__.py` | New — package init |
| `graphrag/observability/trace.py` | New — Span, QueryTrace dataclasses |
| `graphrag/llm/router.py` | Add `answer_with_trace()`, instrument classify/retrieve |
| `graphrag/backends/hana_backend.py` | Add span recording to protocol methods |
| `graphrag/backends/networkx_backend.py` | Same |
| `graphrag/llm/genai_hub.py` | Add timing/token estimation to chat/chat_stream |
| `graphrag/api.py` | Add `include_trace` param, trace endpoint |

---

## Phase 2: Relational MCP Tools

### Goal

Add MCP tools for direct relational queries that don't need graph traversal — aggregations, filters, rankings on base tables. These complement the existing 10 graph tools.

### 2a. New backend protocol methods

**Modified file:** `graphrag/backends/protocol.py`

Add 6 new methods:

```python
# Spend analysis
def get_spend_by_vendor(top_n: int = 10) -> list[dict]
    """Top vendors by total PO spend."""

def get_spend_by_category(top_n: int = 10) -> list[dict]
    """Spend aggregated by material category."""

# PO analysis
def get_pos_by_filter(status: str | None, maverick: bool | None,
                      min_value: float | None, max_value: float | None,
                      limit: int = 20) -> list[dict]
    """Filter POs by status, maverick flag, and/or value range."""

# Invoice analysis
def get_invoice_aging() -> list[dict]
    """Invoice aging summary: counts by match_status and payment status."""

def get_overdue_invoices(limit: int = 20) -> list[dict]
    """Invoices past due (payment_due_date < today, not fully paid)."""

# Vendor risk
def get_vendor_risk_summary(threshold: float = 3.0) -> list[dict]
    """Vendors with risk_score above threshold, with quality and delivery metrics."""
```

### 2b. Implement in both backends

**HANA backend** — Direct SQL on base tables (not vertex/edge views):

```sql
-- Example: get_spend_by_vendor
SELECT v.vendor_id, v.vendor_name_1, SUM(p.total_value) as total_spend,
       COUNT(DISTINCT p.po_id) as po_count
FROM "{schema}"."vendor_master" v
JOIN "{schema}"."po_header" p ON p.vendor_id = v.vendor_id
GROUP BY v.vendor_id, v.vendor_name_1
ORDER BY total_spend DESC
LIMIT ?
```

**NetworkX backend** — Pandas operations on the underlying CSV data (already loaded for graph construction). Add a `_tables` dict that holds raw DataFrames alongside the graph.

### 2c. New MCP tools

**Modified file:** `graphrag/mcp_server.py`

Add 6 tools mapping to the new protocol methods:

```python
@mcp.tool()
def get_top_vendors_by_spend(top_n: int = 10) -> str
@mcp.tool()
def get_spend_by_category(top_n: int = 10) -> str
@mcp.tool()
def filter_purchase_orders(status: str | None = None, maverick_only: bool = False,
                           min_value: float | None = None, max_value: float | None = None) -> str
@mcp.tool()
def get_invoice_aging_summary() -> str
@mcp.tool()
def get_overdue_invoices() -> str
@mcp.tool()
def get_high_risk_vendors(risk_threshold: float = 3.0) -> str
```

### 2d. Add to router intent patterns

**Modified file:** `graphrag/llm/prompts.py`

Add new patterns to the router prompt:
- `spend_by_vendor` — "Who are our top vendors by spend?"
- `spend_by_category` — "What's our spend breakdown by category?"
- `po_filter` — "Show me all maverick POs over $50K"
- `invoice_aging` — "What's our invoice aging?"
- `overdue_invoices` — "Which invoices are overdue?"
- `vendor_risk` — "Show high-risk vendors"

**Modified file:** `graphrag/llm/router.py`

Add 6 new cases to `retrieve()` match-case and to `_fallback_classify()`.

### 2e. New context formatters

**Modified file:** `graphrag/retrieval/context_formatter.py`

Add formatters:
- `format_spend_table(items, title)` — tabular with vendor/category, spend, count
- `format_po_list(items)` — PO ID, vendor, value, status, maverick flag
- `format_invoice_aging(items)` — match_status buckets with counts and totals
- `format_vendor_risk(items)` — vendor, risk_score, quality_score, on_time_%

### Files changed (Phase 2)

| File | Change |
|------|--------|
| `graphrag/backends/protocol.py` | Add 6 relational methods |
| `graphrag/backends/hana_backend.py` | Implement with SQL on base tables |
| `graphrag/backends/networkx_backend.py` | Implement with pandas on loaded CSVs |
| `graphrag/mcp_server.py` | Add 6 MCP tools (total: 16) |
| `graphrag/llm/prompts.py` | Add 6 intent patterns to router prompt |
| `graphrag/llm/router.py` | Add 6 retrieve cases + fallback patterns |
| `graphrag/retrieval/context_formatter.py` | Add 4 formatters |

---

## Phase 3: UI

### Goal

A React single-page app that provides:
1. **Chat interface** — Ask procurement questions, see answers
2. **Graph visualization** — Interactive node/edge rendering showing entities and relationships traversed
3. **Trace panel** — Expandable side panel showing the full query pipeline: intent, tools called, nodes visited, LLM call details, timing waterfall

### Tech stack

| Layer | Choice | Why |
|-------|--------|-----|
| Framework | React 18 + TypeScript | Modern, widely supported |
| Graph viz | **Cytoscape.js** (via react-cytoscapejs) | Best for directed graphs with typed nodes/edges, good layout algorithms, lightweight |
| Styling | Tailwind CSS | Fast iteration, clean look |
| Build | Vite | Fast dev server, simple config |
| State | React hooks (useState/useContext) | Sufficient for this scope |
| HTTP | fetch API | No need for axios at this scale |

### 3a. Project structure

```
ui/
  package.json
  vite.config.ts
  tsconfig.json
  tailwind.config.js
  public/
    index.html
  src/
    main.tsx
    App.tsx
    api/
      client.ts              # fetch wrapper for /chat, /health
    components/
      ChatPanel.tsx           # Question input + answer display
      GraphView.tsx           # Cytoscape.js graph visualization
      TracePanel.tsx          # Observability: spans, timing waterfall
      NodeDetail.tsx          # Click a node → show entity details
      Header.tsx              # App header with status indicator
    hooks/
      useChat.ts              # Chat state management
      useGraph.ts             # Graph data from trace → Cytoscape elements
    types/
      index.ts                # ChatResponse, QueryTrace, Span, GraphNode, GraphEdge
    styles/
      globals.css             # Tailwind imports + custom node/edge colors
```

### 3b. Layout (three-panel)

```
┌─────────────────────────────────────────────────────────┐
│  Header: "Procurement Knowledge Graph"   [HANA] [●]     │
├──────────────┬──────────────────────┬───────────────────┤
│              │                      │                   │
│  Chat Panel  │    Graph View        │   Trace Panel     │
│  (left)      │    (center)          │   (right)         │
│              │                      │                   │
│  [Ask...]    │   ○ VND-NIDEC-JP     │   ▸ classify 42ms │
│              │   │                  │   ▸ retrieve 85ms │
│  Q: Who      │   ├─ SUPPLIES ──○    │     └ get_vendor  │
│  supplies    │   │  MAT-BATT-001   │       _profile    │
│  battery     │   │                  │       3 queries   │
│  cells?      │   ├─ HAS_CONTRACT   │   ▸ generate 1.2s │
│              │   │  ──○ CTR-001    │     └ tokens: 847 │
│  A: Three    │   │                  │                   │
│  vendors...  │   └─ ORDERED_FROM   │   Total: 1.33s    │
│              │      ──○ PO-00042   │                   │
│              │                      │                   │
├──────────────┴──────────────────────┴───────────────────┤
│  Node Detail (bottom, appears on click)                  │
│  VND-NIDEC-JP | Quality: 4.2 | Risk: 1.8 | On-time: 94%│
└─────────────────────────────────────────────────────────┘
```

### 3c. Graph visualization details

**Node styling by entity type:**

| Type | Color | Shape |
|------|-------|-------|
| VENDOR | Blue | Round rectangle |
| MATERIAL | Green | Ellipse |
| PURCHASE_ORDER | Orange | Rectangle |
| CONTRACT | Purple | Diamond |
| INVOICE | Red | Rectangle |
| GOODS_RECEIPT | Teal | Hexagon |
| PAYMENT | Gold | Ellipse |
| PLANT | Gray | Triangle |
| CATEGORY | Pink | Round rectangle |
| PURCHASE_REQ | Cyan | Rectangle |

**Edge styling:**
- Labeled with edge type (SUPPLIES, ORDERED_FROM, etc.)
- Directed arrows
- Highlighted edges for the current query's traversal path (thicker, animated)

**Interactions:**
- Click node → NodeDetail panel shows full entity attributes
- Click node → secondary query to `GET /chat?include_trace=true` for that entity
- Hover edge → tooltip with edge attributes
- Zoom/pan/fit on the graph
- Layout: dagre (hierarchical left-to-right) for P2P chains, cose (force-directed) for vendor/material networks

**Data flow:**
- `QueryTrace.graph_nodes` → Cytoscape node elements (fetch full attributes via `get_entity`)
- `QueryTrace.graph_edges` → Cytoscape edge elements
- Previous query results stay on graph (accumulate), new ones highlighted
- "Clear graph" button to reset

### 3d. Trace panel details

**Waterfall view:**
- Horizontal bars showing timing for each span
- Nested: classify → (LLM call), retrieve → (backend call 1, backend call 2, ...), generate → (LLM call)
- Color-coded: LLM calls = blue, backend calls = green, formatting = gray

**Details per span:**
- classify: pattern detected, entity_id extracted, fallback used?
- retrieve: backend method called, SQL query (for HANA), result count, entity IDs in result
- generate: model name, estimated tokens (in/out), latency

**Collapsible sections:**
- Intent classification result (JSON)
- Context sent to LLM (expandable, shows formatted markdown)
- Raw LLM response

### 3e. Chat panel details

- Input box with submit button (Enter key)
- Message history (scrollable)
- Each answer shows:
  - Answer text (markdown rendered)
  - Source entity IDs as clickable badges (click → highlight on graph + fetch details)
  - Query pattern badge (e.g., "vendor_profile", "p2p_chain")
  - Timing badge (e.g., "1.3s")
- Streaming support (SSE) for real-time token display

### 3f. API client

```typescript
// api/client.ts
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface ChatRequest {
  question: string
  stream?: boolean
  include_trace?: boolean
}

interface ChatResponse {
  answer: string
  sources: string[]
  query_pattern: string
  context_snippet: string
  trace?: QueryTrace
}

async function chat(req: ChatRequest): Promise<ChatResponse>
async function* chatStream(req: ChatRequest): AsyncGenerator<string>
async function health(): Promise<{status: string}>
```

### Files created (Phase 3)

All under `ui/` — approximately 15 files. No changes to existing `graphrag/` code (consumes the API built in Phase 1).

---

## Phase 4: CF Deployment

### Goal

Deploy the REST API (FastAPI) and UI (static React build) as a single CF app on SAP BTP.

### 4a. Build configuration

**New file:** `manifest.yml`

```yaml
applications:
  - name: procurement-graphrag
    memory: 512M
    disk_quota: 1G
    buildpacks:
      - python_buildpack
    command: python -m graphrag.api --host 0.0.0.0 --port $PORT
    env:
      GRAPH_BACKEND: hana
      HANA_HOST: <from-env>
      HANA_PORT: 443
      HANA_USER: DBADMIN
      HANA_PASSWORD: <from-env>
      HANA_SCHEMA: PROCUREMENT
      AICORE_AUTH_URL: <from-env>
      AICORE_CLIENT_ID: <from-env>
      AICORE_CLIENT_SECRET: <from-env>
      AICORE_RESOURCE_GROUP: default
      AICORE_BASE_URL: <from-env>
      GENAI_MODEL_NAME: anthropic--claude-4.6-opus
    services:
      - procurement-hana    # HANA Cloud service binding (optional, can use env vars)
```

### 4b. Serve UI from FastAPI

**Modified file:** `graphrag/api.py`

- Mount static files: `app.mount("/", StaticFiles(directory="ui/dist", html=True))`
- Build step: `cd ui && npm run build` before `cf push`
- The API endpoints (`/chat`, `/health`, `/traces`) stay at their paths
- The UI is served from `/` (SPA fallback to `index.html`)

### 4c. Production requirements

**New file:** `runtime.txt`

```
python-3.13.x
```

**New file (or update):** `requirements.txt`

Generated from `pip freeze` with only the graphrag + hana deps. CF python_buildpack reads this.

### 4d. Deploy script

**New file:** `scripts/deploy_to_cf.sh`

```bash
#!/bin/bash
set -euo pipefail

echo "=== Build UI ==="
cd ui && npm ci && npm run build && cd ..

echo "=== Deploy to CF ==="
cf push procurement-graphrag

echo "=== Set secrets (first deploy only) ==="
# cf set-env procurement-graphrag HANA_PASSWORD <value>
# cf set-env procurement-graphrag AICORE_CLIENT_SECRET <value>
# cf restage procurement-graphrag
```

### 4e. MCP Server on CF

The MCP server uses streamable-http transport for CF:

```yaml
# Optional second app for MCP gateway integration
  - name: procurement-mcp
    memory: 256M
    command: python -m graphrag.mcp_server --transport streamable-http --port $PORT
    env:
      GRAPH_BACKEND: hana
      # ... same env vars as above
```

### Files changed (Phase 4)

| File | Change |
|------|--------|
| `manifest.yml` | New — CF deployment manifest |
| `runtime.txt` | New — Python version for CF |
| `requirements.txt` | New or update — pinned deps for CF |
| `scripts/deploy_to_cf.sh` | New — Build + push script |
| `graphrag/api.py` | Mount static files from `ui/dist/` |

---

## Dependency Graph

```
Phase 1: Observability ──────┐
                              ├──> Phase 3: UI ──> Phase 4: CF Deploy
Phase 2: Relational Tools ───┘
```

Phases 1 and 2 are independent of each other and can be built in parallel.
Phase 3 depends on both (consumes traces + relational tools).
Phase 4 depends on Phase 3 (packages everything).

---

## Estimated Scope

| Phase | New files | Modified files | Complexity |
|-------|-----------|---------------|------------|
| 1. Observability | 2 | 5 | Medium — threading trace context through pipeline |
| 2. Relational tools | 0 | 7 | Low-medium — SQL queries + formatters + router patterns |
| 3. UI | ~15 | 1 | Medium-high — React app + Cytoscape.js graph viz |
| 4. CF Deploy | 3-4 | 1 | Low — manifest + build script |

---

## Open Questions

1. **Graph viz library** — Cytoscape.js is proposed. Alternative: vis.js (simpler but less graph-specific), D3.js (more control but more work), react-force-graph (3D capable, WebGL). Cytoscape.js has the best balance for directed typed graphs.

2. **Trace storage** — Plan says in-memory LRU (last 50 traces). If persistence is needed later, could add SQLite or just append to a JSONL file.

3. **Auth on CF** — No auth in the plan. If the CF app should be protected, can add SAP BTP XSUAA (OAuth2) later. For demo purposes, open is fine.

4. **MCP server on CF** — Separate app or same app? Plan shows separate. Could consolidate if memory is tight.

5. **Streaming in UI** — SSE streaming works for chat answers. For graph viz, we need the full trace before rendering. Could show a "loading graph..." state while streaming the answer, then render graph when trace arrives.
