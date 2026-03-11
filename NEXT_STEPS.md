# Next Steps

## What's Done

- Data generator: 18-stage pipeline, 29 tables, ~10K rows at 1x scale, 12 seed scenarios
- Exporters: CSV, basic SQL, HANA Cloud SQL, Postgres SQL
- Deployment: HANA Cloud (Python/hdbcli) + EC2 Postgres (Bash/SSH)
- ML pipeline: UC-02 Invoice Three-Way Match (preprocessing, feature engineering, 4-model training, inference, SAP AI Core Dockerfiles)
- Documentation: README, ARCHITECTURE, DEPLOYMENT, ML_USE_CASES, CLAUDE.md

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
- [ ] Add retrieval-augmented generation (RAG) for procurement domain context
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
