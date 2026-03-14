# Next Steps

## What's Done

- Data generator: 18-stage pipeline, 29 tables, ~10K rows at 1x scale, 12 seed scenarios
- Exporters: CSV, basic SQL, HANA Cloud SQL, Postgres SQL
- Deployment: HANA Cloud (Python/hdbcli) + EC2 Postgres (Bash/SSH)
- Knowledge graph: HANA Cloud GRAPH WORKSPACE (10 vertex views, 14 edge views, unified views, deploy script with `--dry-run` and `--no-graph` fallback)
- ML pipeline: UC-02 Invoice Three-Way Match (preprocessing, feature engineering, 4-model training, inference, SAP AI Core Dockerfiles)
- Documentation: README, ARCHITECTURE, DEPLOYMENT, ML_USE_CASES, CLAUDE.md

---

## 0. Graph Workspace — Your Action Items

The knowledge graph SQL and deploy script are ready. You need to deploy and validate on your HANA Cloud instance.

### Prerequisites

- [ ] Relational data already loaded to HANA Cloud (`python scripts/deploy_to_hana.py`)
- [ ] `.env` configured with HANA Cloud credentials (`HANA_HOST`, `HANA_PORT`, `HANA_USER`, `HANA_PASSWORD`, `HANA_SCHEMA`)
- [ ] `hdbcli` installed (`pip install -e ".[hana]"`)

### Deploy & Validate

```bash
# 1. Preview the 54 SQL statements that will execute
python scripts/graph/deploy_graph.py --dry-run

# 2. Deploy the graph workspace
python scripts/graph/deploy_graph.py

# 3. If graph engine is not available on your instance, use SQL-only mode
python scripts/graph/deploy_graph.py --no-graph
```

### Post-Deploy Verification (run in HANA SQL console)

```sql
-- Check vertex counts by type
SELECT vertex_type, COUNT(*) FROM "PROCUREMENT"."V_ALL_VERTICES" GROUP BY vertex_type ORDER BY vertex_type;

-- Check edge counts by type
SELECT edge_type, COUNT(*) FROM "PROCUREMENT"."E_ALL_EDGES" GROUP BY edge_type ORDER BY COUNT(*) DESC;

-- Verify graph workspace exists
SELECT * FROM GRAPH_WORKSPACES WHERE SCHEMA_NAME = 'PROCUREMENT';

-- Test a graph traversal: find all POs for a specific vendor (2-hop)
SELECT v2.vertex_id, v2.vertex_type, v2.label
FROM "PROCUREMENT"."V_ALL_VERTICES" v1
JOIN "PROCUREMENT"."E_ALL_EDGES" e ON e.source_vertex = v1.vertex_id
JOIN "PROCUREMENT"."V_ALL_VERTICES" v2 ON v2.vertex_id = e.target_vertex
WHERE v1.vertex_id = 'VND-SG-00001' AND e.edge_type = 'HAS_CONTRACT';

-- Test a multi-hop query: Vendor → Contract → PO (via under_contract edges)
SELECT v.vertex_id AS vendor, e1.target_vertex AS contract, e2.source_vertex AS po
FROM "PROCUREMENT"."E_ALL_EDGES" e1
JOIN "PROCUREMENT"."E_ALL_EDGES" e2 ON e2.target_vertex = e1.target_vertex
WHERE e1.edge_type = 'HAS_CONTRACT' AND e2.edge_type = 'UNDER_CONTRACT'
LIMIT 20;
```

### Expected Results (at 1x scale)

| Vertex Type | Approx Count |
|-------------|-------------|
| VENDOR | 120 |
| MATERIAL | 800 |
| PLANT | 8 |
| CATEGORY | ~79 |
| PURCHASE_ORDER | 400 |
| CONTRACT | 40 |
| INVOICE | 320 |
| GOODS_RECEIPT | 350 |
| PAYMENT | ~260 |
| PURCHASE_REQ | 500 |
| **Total vertices** | **~2,877** |
| **Total edges** | **~8,500** |

### Recommended Next Steps for the Graph

- [ ] **Connect a GenAI agent**: Use SAP GenAI Hub to build a GraphRAG agent that traverses the graph for procurement Q&A (e.g., "Which vendors supply materials for plant 1000?", "Show the full procure-to-pay chain for PO-00001")
- [ ] **Add graph algorithms**: Once the GRAPH WORKSPACE is live, use HANA's built-in algorithms (shortest path, BFS, neighborhood) for supply chain analysis
- [ ] **Add more edge types**: Consider edges for `PR → PO` (pr_id linkage on po_line_item), `Material → Plant` (via material_plant_extension), `Vendor → Plant` (via source_list aggregation)

---

## 1. HANA Cloud Validation

Verify the HANA Cloud exporter against a real BTP instance.

- [ ] Provision a HANA Cloud trial instance on SAP BTP
- [ ] Configure `.env` with real credentials
- [ ] Run `python scripts/deploy_to_hana.py` and verify all 29 tables load
- [ ] Spot-check a few tables via SQL console (row counts, FK joins, seed scenarios)
- [ ] Test idempotent re-deployment (run the script twice)

## 2. GenAI Demo Application

The data exists to power a GenAI demo. The demo app itself is the next major deliverable.

- [ ] Define demo scenarios and user flows (which of the 12 seeds to showcase)
- [ ] Choose GenAI framework (SAP GenAI Hub, LangChain, or direct Claude/GPT API)
- [ ] Build a natural-language-to-SQL interface over the HANA Cloud schema
- [ ] Add GraphRAG over the knowledge graph for multi-hop procurement queries
- [ ] Create a UI (SAP Fiori, Streamlit, or similar)
- [ ] Wire in ML model predictions (UC-02 match status, vendor risk, etc.) as tool calls

## 3. ML Use Cases — Tier 1 (High Impact)

These are the most impactful use cases for the demo. UC-02 is done; three remain.

- [ ] **UC-01: Maverick PO Detection** — Binary classifier on `po_header.maverick_flag`. Data already has 5-8% maverick rate. Follow the UC-02 pattern (preprocessing, feature engineering, 4-model training, inference).
- [ ] **UC-03: Vendor Risk Scoring** — Regression/ranking on `vendor_master.risk_score`. Leverage the existing shared feature store (vendor profile, performance). Strong demo value.
- [ ] **UC-04: Price Anomaly Detection** — Unsupervised anomaly scoring on `po_line_item`. SEED-010 (connector price > standard cost) provides a ground-truth anchor. Consider isolation forest or autoencoder.

## 4. ML Use Cases — Tier 2 (Medium Impact)

- [ ] **UC-05: Delivery Delay Prediction** — Predict `actual_delivery_date > requested_delivery_date` from PO/vendor/material features
- [ ] **UC-06: Contract Renewal Prediction** — Predict renewal likelihood from contract utilization, vendor performance, spend trends
- [ ] **UC-07: Payment Timing Optimization** — Predict optimal payment date balancing early-payment discounts vs. cash flow
- [ ] **UC-08: Spend Concentration Risk** — Compute HHI (Herfindahl-Hirschman Index) per category, flag concentration risk

## 5. ML Use Cases — Tier 3 (Specialized)

- [ ] **UC-09: GR Quality Prediction** — Predict `quantity_rejected > 0` from vendor quality scores, material type, historical rejection rates
- [ ] **UC-10: PR Priority Scoring** — Classify PR priority from requester department, material criticality, delivery urgency
- [ ] **UC-11: Duplicate Invoice Detection** — Flag duplicate invoices using fuzzy matching on vendor, amount, date proximity
- [ ] **UC-12: Spend Classification** — Predict material category from PO line item descriptions (NLP + classification)
- [ ] **UC-13: Confidentiality Tier Prediction** — Predict `material_master.confidentiality_tier` from material attributes

## 6. ML Infrastructure

- [ ] **Monitoring** — Model drift detection, prediction quality tracking, alerting
- [ ] **Retraining pipeline** — Scheduled retraining with new data, model versioning, A/B deployment
- [ ] **SAP AI Core deployment** — Push training + inference containers to SAP AI Core (CF or Kyma runtime)
- [ ] **Feature store materialization** — Deploy `feature_store_views.sql` to HANA Cloud, schedule refresh

## 7. Testing & Quality

- [ ] Add unit tests for existing generators (currently only `test_hana_exporter.py` exists)
- [ ] Add integration test that runs the full pipeline at scale 1 and asserts row counts
- [ ] Add field-length validation (check `max(len(field)) <= VARCHAR(N)` for every column before export)
- [ ] Add CI pipeline (GitHub Actions: lint, test, generate at scale 1)

## 8. Data Enhancements

- [ ] **Scale 10x validation** — Run at `--scale 10` and verify statistical distributions still hold (~106K rows)
- [ ] **Incremental generation** — Support appending new transactional data to an existing dataset (currently full regeneration only)
- [ ] **Time-series patterns** — Add seasonal procurement patterns (Q4 budget flush, summer slowdowns)
- [ ] **Multi-currency** — Expand beyond SGD to include USD, EUR, JPY line items with realistic FX rates
- [ ] **More realistic text** — Use LLM-generated PR descriptions, rejection reasons, invoice notes for NLP use cases

---

## Suggested Priority Order

1. **HANA Cloud validation** — quick win, unblocks everything downstream
2. **UC-01 Maverick PO Detection** — straightforward binary classifier, reuses UC-02 infrastructure
3. **UC-03 Vendor Risk Scoring** — high demo value, shared feature store already has the features
4. **GenAI demo app** — the reason all this data exists
5. **Testing & CI** — protect against regressions as use cases multiply
6. **Remaining ML use cases** — build out in tier order (4 > 5 > 6)
