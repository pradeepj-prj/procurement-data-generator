# Demo Scenarios

Three guided storylines demonstrating how the Procurement Knowledge Graph app helps different personas solve real problems. Each scenario follows a persona through a sequence of queries that build on each other, showing how the graph, trace, and chat panels work together.

---

## Scenario 1: The Invoice Investigator

**Persona:** Mei Lin, Accounts Payable Analyst at the Singapore HQ. She processes vendor invoices and resolves payment blocks. Her KPI is reducing the average time to clear blocked invoices from 14 days to 7 days.

**Problem:** Mei Lin starts her Monday morning with 42 blocked invoices in the system. She needs to understand the root causes, prioritize which to resolve first, and decide whether to accept or dispute each variance.

### Query sequence

**Step 1 — Get the big picture**

> "What's our invoice aging?"

*Pattern: `invoice_aging`*

Mei Lin sees the breakdown: 245 FULL_MATCH, 42 PRICE_VARIANCE, 18 QUANTITY_VARIANCE, 8 BOTH_VARIANCE. She now knows the scale of the problem — 68 invoices need attention, and price mismatches are the dominant issue.

**Step 2 — Find the blocked invoices**

> "Show me invoices with matching problems"

*Pattern: `invoice_issues`*

The system returns all 68 problematic invoices. Mei Lin spots INV-000001 from VND-MOLEX-SG (PRICE_VARIANCE, $11,213.60, payment blocked) and INV-000017 from VND-NIDEC-MY (BOTH_VARIANCE, $9,720.18, payment blocked). She decides to investigate the highest-value one first.

*Graph panel now shows invoice nodes in red.*

**Step 3 — Investigate the top blocked invoice**

> "What's wrong with INV-000001?"

*Pattern: `invoice_context`*

The three-way match context reveals:
- Invoice amount: $11,213.60 from VND-MOLEX-SG
- Linked PO (PO-000038): original order value and unit prices
- Goods receipt: confirms materials were received
- Block reason: PRICE_MISMATCH

Mei Lin can now compare the PO price vs. invoice price line by line. She sees the vendor increased the unit price by 8% without a contract amendment.

*Graph panel shows the full chain: INV-000001 → PO-000038 → VND-MOLEX-SG, plus materials and GR nodes.*

**Step 4 — Check the vendor's track record**

> "Tell me about VND-MOLEX-SG"

*Pattern: `vendor_profile`*

Mei Lin sees VND-MOLEX-SG has quality score 92, on-time delivery 96.1%, and an active contract. This is a reliable vendor — the price increase is likely legitimate (raw material cost pass-through), not an error. She decides to accept the variance and request a contract amendment for future orders.

*Graph panel accumulates — VND-MOLEX-SG node now connects to its materials and contracts alongside the invoice chain.*

**Step 5 — Check for overdue payments**

> "Which invoices are overdue?"

*Pattern: `overdue_invoices`*

She finds several invoices past their payment due date. Resolving the blocked invoices quickly is critical — late payments damage vendor relationships and may trigger penalty clauses.

### Demo takeaway

The app lets Mei Lin go from "68 blocked invoices" to "here's exactly why this invoice is blocked and whether to accept or dispute it" in 5 queries, with the graph showing the full document chain at each step.

---

## Scenario 2: The Supply Chain Risk Manager

**Persona:** Raj Krishnan, Supply Chain Risk Manager. He reports to the VP of Operations and is responsible for identifying and mitigating supply disruptions before they impact production at the three APAC plants (SG01, MY01, VN01).

**Problem:** A typhoon warning has been issued for southern Japan, where several key vendors are located. Raj needs to quickly assess: which vendors are in the affected region, what materials they supply, whether there are alternative vendors, and what the production impact could be.

### Query sequence

**Step 1 — Identify high-risk vendors**

> "Show me high-risk vendors"

*Pattern: `vendor_risk`*

Raj sees vendors sorted by risk score. VND-HOKUYO (Japan, risk score 72, quality 82, on-time 88.5%) and VND-NIDEC-JP (Japan, risk score varies) stand out — both are Japanese vendors that could be affected by the typhoon.

**Step 2 — Assess VND-HOKUYO's exposure**

> "Tell me about VND-HOKUYO"

*Pattern: `vendor_profile`*

Raj sees VND-HOKUYO supplies 17 materials including MAT-LIDAR-2D (2D LiDAR Scanner) — a HIGH-criticality component. They have contract CTR-00001 (QUANTITY, active). Their on-time delivery is already at 88.5% — lower than average, suggesting existing logistics challenges.

*Graph shows VND-HOKUYO connected to all its materials and contracts.*

**Step 3 — Check for alternative suppliers**

> "Who supplies MAT-LIDAR-2D?"

*Pattern: `material_vendors`*

**This is the critical finding**: MAT-LIDAR-2D is single-sourced — VND-HOKUYO is the only approved vendor. If the typhoon disrupts their operations, there is no backup supplier for this critical component. Production lines at MY01 that use LiDAR scanners would halt.

*Graph highlights the single-source dependency — one edge from MAT-LIDAR-2D to VND-HOKUYO with no alternatives.*

**Step 4 — Check which plants are affected**

> "What materials are sourced at MY01?"

*Pattern: `plant_materials`*

Raj confirms MAT-LIDAR-2D is sourced at the Penang production plant (MY01). He cross-references with VND-HOKUYO's other materials to see the full impact scope at this plant.

**Step 5 — Review contract and recent orders**

> "What POs are under CTR-00001?"

*Pattern: `contract_pos`*

Raj sees the volume of orders placed under this contract — helping him estimate the financial exposure and how much buffer inventory might exist based on recent delivery dates.

**Step 6 — Check the top spend concentration**

> "Who are our top vendors by spend?"

*Pattern: `spend_by_vendor`*

Raj sees VND-CATL (18 POs) and VND-NIDEC-JP (14 POs) dominate spend. Combined with the single-source analysis, he now has a complete risk picture to present to the VP.

### Demo takeaway

In 6 queries, Raj went from "typhoon warning" to a concrete risk assessment: VND-HOKUYO is the single source for a critical LiDAR component at the Penang plant, with an already-elevated risk score of 72 and below-average delivery performance. He can now recommend: expedite a safety stock order, begin qualifying an alternative LiDAR vendor, and set up monitoring for the other Japanese vendors.

---

## Scenario 3: The Procurement Compliance Auditor

**Persona:** Sarah Chen, Internal Audit Manager. She conducts quarterly procurement compliance reviews, looking for policy violations like maverick purchasing (buying outside contracts), unauthorized spend, and expired contract coverage gaps.

**Problem:** It's Q1 audit time. Sarah needs to identify maverick purchases, understand why they happened, check contract coverage, and quantify the financial exposure from non-compliant buying.

### Query sequence

**Step 1 — Find all maverick purchases**

> "Show me all maverick POs"

*Pattern: `po_filter` with maverick=true*

Sarah sees 20-30 maverick POs flagged in the system. She notices a cluster: PO-000027, PO-000028, PO-000029 — all from VND-NIDEC-JP, totaling ~$14,000. Three maverick POs from the same vendor is a pattern worth investigating.

**Step 2 — Trace the first maverick PO**

> "Show me the P2P chain for PO-000027"

*Pattern: `p2p_chain`*

Sarah sees PO-000027 was placed with VND-NIDEC-JP on 2025-02-04 for $4,892.23, status FULLY_RECEIVED. It's flagged maverick because it wasn't placed under an existing contract. She checks: was there a contract available that should have been used?

*Graph shows PO-000027 connected to VND-NIDEC-JP and its materials — but no UNDER_CONTRACT edge (because it's maverick).*

**Step 3 — Check if a contract exists**

> "What contracts do we have with VND-NIDEC-JP?"

*Pattern: `vendor_contracts`*

Sarah finds VND-NIDEC-JP has active contracts. So why were these 3 POs placed as maverick? Possible reasons: the buyer bypassed the contract, the materials weren't covered by the contract scope, or the contract was expired at the time of purchase. She notes this for the audit finding.

*Graph now shows VND-NIDEC-JP connected to both the maverick POs (no contract edge) and the contracts (HAS_CONTRACT edges) — visually highlighting the gap.*

**Step 4 — Check for expired contracts**

> "Show me the ELEC category tree"

*Pattern: `category_tree`*

Sarah explores the category hierarchy to understand what materials VND-NIDEC-JP supplies and which categories might have contract gaps. She cross-references with the vendor profile.

**Step 5 — Assess overall spend compliance**

> "What's our spend by category?"

*Pattern: `spend_by_category`*

Sarah sees total spend by category. She can now calculate what percentage of Electronics spend is covered by active contracts vs. maverick purchases.

**Step 6 — Quantify the vendor concentration risk**

> "Who are our top vendors by spend?"

*Pattern: `spend_by_vendor`*

VND-NIDEC-JP is the #2 vendor by spend with 14 POs. Three of those are maverick — that's 21% non-compliant buying from a top-3 vendor. This is a material audit finding.

### Demo takeaway

Sarah's audit found: 3 maverick POs totaling $14,058 from VND-NIDEC-JP despite active contracts being available, representing a 21% non-compliance rate for a top vendor. Her audit report recommends: mandatory contract reference for all VND-NIDEC-JP orders, buyer training on contract utilization, and a quarterly maverick spend dashboard. The graph visualization clearly shows the missing contract edges on maverick POs — a compelling visual for the audit committee presentation.

---

## Running the Demos

**Cloud Foundry (recommended):** Open the deployed app at your CF URL (e.g., `https://procurement-graphrag.cfapps.ap10.hana.ondemand.com`). Uses HANA Cloud backend with live data.

**Local development:**
```bash
# Terminal 1: API (NetworkX backend, no HANA needed)
GRAPH_BACKEND=networkx uvicorn graphrag.api:app --port 8000

# Terminal 2: UI
cd ui && npm run dev
```

Open the app and follow each scenario's query sequence. The graph panel accumulates nodes across queries, building up the visual story. Use "Clear" between scenarios to reset the graph.

**Tips for presenting:**
- Start each scenario by explaining the persona and their problem
- After each query, point out the graph panel — show how entities connect across queries
- Expand the trace panel to show the classify → retrieve → generate pipeline
- Click on nodes in the graph to highlight them
- The chat panel preserves history, so you can scroll back to show the progression

**Agent mode bonus:** For each scenario, try the final "synthesis" question in Agent mode (click the purple Agent button in the header). For example:
- Scenario 1: "Find all blocked invoices from VND-MOLEX-SG and check their vendor's quality history" — the agent will chain search → invoice context → vendor profile automatically
- Scenario 2: "Which critical materials at MY01 are single-sourced from high-risk vendors?" — the agent will chain plant materials → material vendors → vendor profiles
- Scenario 3: "Find maverick POs from VND-NIDEC-JP and check if they have active contracts" — the agent will chain PO filter → vendor contracts → compare

The chat panel shows **live step visibility** in agent mode — instead of "Thinking...", you see each reasoning step and tool call as it happens (via SSE streaming). Follow-up questions work naturally thanks to conversation history (e.g., "Which of those have the best quality scores?" after a vendor list query).

The trace panel shows the complete span tree for each agent execution.
