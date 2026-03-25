# GraphRAG Query Patterns

This document explains the 22 query patterns supported by the Procurement GraphRAG system. Each pattern represents a type of question a user can ask about procurement data. The system classifies every incoming question into one of these patterns, then retrieves the relevant data from the knowledge graph to answer it.

Written for readers who may be new to procurement processes.

---

## How It Works

The system supports two modes:

### Router Mode (default)

When you ask a question:

1. **Classify** — An LLM reads your question and picks one of the 22 patterns below, along with any entity ID you mentioned (e.g., `VND-HOKUYO`, `PO-000001`)
2. **Retrieve** — The system runs a pre-defined graph traversal or database query for that pattern
3. **Generate** — The retrieved data is formatted as structured text and given to the LLM, which writes a natural language answer grounded in that data

This is fast (~14s) but limited to one pattern per question.

### Agent Mode (opt-in)

For complex questions requiring multiple tools:

1. **Reason** — A ReAct agent (LangGraph + gpt-5) reads your question and decides which tool(s) to call
2. **Execute** — The agent calls one or more of the 16 tools below, observes results
3. **Iterate** — The agent reasons about the results and decides if it needs more information, calling additional tools as needed
4. **Answer** — Once the agent has enough context, it synthesizes a final answer

This handles multi-step questions like "Which vendors supply lidar sensors and what are their risk scores?" (requires: search → get vendors → get profiles → synthesize). Toggle via the Agent button in the UI header or `"mode": "agent"` in the API.

---

## Procurement Basics

An AMR (Autonomous Mobile Robot) manufacturer buys materials from vendors to assemble robots. The procurement process — called **Procure-to-Pay (P2P)** — flows like this:

```
Purchase Requisition → Purchase Order → Goods Receipt → Invoice → Payment
       (PR)                (PO)            (GR)          (INV)     (PAY)
```

Supporting entities include **vendors** (who sell materials), **contracts** (negotiated agreements with vendors), **materials** (components like LiDAR scanners, motors, batteries), **plants** (factories in Singapore, Penang, Vietnam), and **categories** (how materials are classified — Electronics, Motion, Power, etc.).

### Entity ID Formats

| Entity | Format | Example |
|--------|--------|---------|
| Vendor | `VND-<code>` | VND-HOKUYO, VND-CATL |
| Material | `MAT-<code>` | MAT-LIDAR-2D, MAT-MOT-400W |
| Purchase Order | `PO-<number>` | PO-000001 |
| Contract | `CTR-<number>` | CTR-00001 |
| Invoice | `INV-<number>` | INV-000001 |
| Goods Receipt | `GR-<number>` | GR-000001 |
| Payment | `PAY-<number>` | PAY-000001 |
| Purchase Req | `PR-<number>` | PR-000001 |
| Plant | `<code>` | SG01, MY01, VN01 |
| Category | `<code>` | ELEC, MOTN, POWR |

---

## Part 1: Graph Traversal Patterns (16)

These patterns traverse the knowledge graph — following relationships (edges) between entities (nodes).

---

### 1. `entity_lookup`

**What it does:** Looks up any single entity by its ID and returns all its attributes.

**When to use:** When you have a specific ID and want to see its details — works for any entity type.

**Example questions:**
- "What is GR-000001?"
- "Look up PAY-000001"
- "Show me PR-000001"

**What you get back:** All attributes of the entity — dates, statuses, amounts, scores, etc.

**Procurement context:** This is a generic lookup. If you know the entity type (vendor, PO, invoice), use the more specific patterns below instead — they return richer data with related entities.

---

### 2. `vendor_profile`

**What it does:** Returns a comprehensive vendor dossier — the vendor's attributes, all materials they supply, their contracts, and total PO count.

**When to use:** When evaluating a vendor's overall relationship with your organization.

**Example questions:**
- "Tell me about VND-HOKUYO"
- "What's the profile for VND-CATL?"
- "Show me vendor Nidec Corporation"

**What you get back:**
- **Vendor attributes**: Name (Hokuyo Automatic Co., Ltd.), country (JP), status, payment terms
- **Performance scores**: Quality (82/100), Risk (72/100), On-time delivery (88.5%), ESG score
- **Materials supplied**: List of materials with plant and preferred ranking (e.g., MAT-LIDAR-2D at plant MY01, rank 1)
- **Contracts**: Active contracts with type, validity dates (e.g., CTR-00001, QUANTITY contract, valid 2024-08 to 2025-08)
- **PO count**: Total purchase orders placed with this vendor

**Procurement context:** Vendor evaluation is critical in procurement. Quality and on-time delivery scores reflect past performance. Risk score flags vendors that may have supply chain issues. ESG (Environmental, Social, Governance) scores track sustainability compliance.

---

### 3. `vendor_materials`

**What it does:** Lists all materials a vendor is approved to supply, based on the source list (approved vendor-material combinations).

**When to use:** When you want to know what a specific vendor can sell you.

**Example questions:**
- "What materials does VND-HOKUYO supply?"
- "What can we buy from CATL?"

**What you get back:** List of materials with plant assignments and preferred ranking. For example, VND-HOKUYO supplies MAT-LIDAR-2D at plant MY01 (rank 1) and several other electronic components.

**Procurement context:** The **source list** is a formal SAP concept — it maps which vendors are approved to supply which materials at which plants. Rank 1 means preferred vendor; rank 2+ are alternatives.

---

### 4. `material_vendors`

**What it does:** The reverse of `vendor_materials` — given a material, finds all approved vendors who can supply it.

**When to use:** When you need to source a specific component and want to see your options.

**Example questions:**
- "Who supplies MAT-LIDAR-2D?"
- "Which vendors can provide battery packs?"
- "Find suppliers for MAT-MOT-400W"

**What you get back:** List of vendors with their quality scores, plant assignments, and ranking.

**Procurement context:** Having multiple vendors for critical materials (dual-sourcing) reduces supply chain risk. If a material has only one vendor (single-source), that's a risk flag.

---

### 5. `po_details`

**What it does:** Returns a purchase order's header, the vendor it was placed with, and all line items (materials ordered with quantities and prices).

**When to use:** When you want to inspect a specific PO's contents.

**Example questions:**
- "Show me PO-000001"
- "What's in purchase order PO-000008?"

**What you get back:**
- **PO header**: Date (2024-05-06), status (FULLY_RECEIVED), total value (9,514 JPY), type (STANDARD), maverick flag
- **Vendor**: VND-HOKUYO (Hokuyo Automatic Co., Ltd.)
- **Line items**: MAT-LIDAR-2D — quantity 67, unit price 142 JPY, net value 9,514 JPY
- **Contract**: CTR-00001 (if the PO is under a contract)

**Procurement context:** A **purchase order** is the formal document sent to a vendor to buy materials. Each PO has line items specifying what to buy, how much, and at what price. The **maverick flag** indicates whether the PO was created outside normal procurement procedures (without a contract or approved source).

---

### 6. `p2p_chain`

**What it does:** Traces the full **Procure-to-Pay chain** for a purchase order — from the PO through goods receipt, invoicing, and payment.

**When to use:** When you want the end-to-end lifecycle of a purchase order. This is the richest single query in the system.

**Example questions:**
- "Show me the P2P chain for PO-000001"
- "Trace the full flow for PO-000008"

**What you get back:**
- **Purchase order**: Header + vendor + line items + contract (same as `po_details`)
- **Goods receipts**: When materials were physically received at the plant (e.g., GR-000133, posted 2024-07-15)
- **Invoices**: Vendor invoices submitted for payment, with match status (FULL_MATCH, PRICE_VARIANCE, etc.)
- **Payments**: Actual payments made against each invoice

**Procurement context:** The P2P chain represents the lifecycle of a purchase:
1. **PO** — "We want to buy 67 LiDAR scanners at 142 JPY each"
2. **Goods Receipt** — "We received the scanners at the plant"
3. **Invoice** — "The vendor sent us a bill for 9,514 JPY"
4. **Three-way match** — System compares PO vs. GR vs. Invoice (quantities and prices). Discrepancies show as PRICE_VARIANCE or QUANTITY_VARIANCE
5. **Payment** — "We paid the vendor"

---

### 7. `contract_pos`

**What it does:** Finds all purchase orders placed under a specific contract.

**When to use:** When auditing contract utilization — are we actually buying through our negotiated agreements?

**Example questions:**
- "What POs are under CTR-00001?"
- "Show me orders under contract CTR-00002"

**What you get back:** List of POs with their dates, values, and statuses.

**Procurement context:** **Contracts** are pre-negotiated agreements with vendors that lock in prices and terms. POs placed under contracts get better pricing. If POs are placed *without* referencing a contract (maverick purchases), the organization may be overpaying.

---

### 8. `vendor_contracts`

**What it does:** Lists all contracts for a specific vendor.

**When to use:** When reviewing the contractual relationship with a vendor.

**Example questions:**
- "What contracts do we have with VND-HOKUYO?"
- "Show contracts for CATL"

**What you get back:** Contract IDs, types (QUANTITY or VALUE), status (ACTIVE/EXPIRED), and validity dates.

**Procurement context:**
- **QUANTITY contracts** commit to buying a certain quantity over the contract period
- **VALUE contracts** commit to a total spend amount
- Expired contracts mean purchases are no longer covered by negotiated terms

---

### 9. `invoice_issues`

**What it does:** Finds all invoices with matching problems — where the three-way match (PO vs. GR vs. Invoice) found discrepancies.

**When to use:** When investigating payment blocks, accounts payable backlogs, or vendor disputes.

**Example questions:**
- "Show me invoices with problems"
- "Which invoices have matching issues?"
- "Find invoice mismatches"

**What you get back:** List of invoices where match_status is not FULL_MATCH, showing the type of variance:
- **PRICE_VARIANCE** — invoice price differs from PO price
- **QUANTITY_VARIANCE** — invoiced quantity differs from received quantity
- **BOTH_VARIANCE** — both price and quantity differ

**Procurement context:** The **three-way match** is a fundamental accounts payable control. When an invoice arrives, the system checks:
1. Does the invoiced price match the PO price?
2. Does the invoiced quantity match the goods received?

Mismatches trigger a **payment block** — the invoice can't be paid until someone investigates and resolves the discrepancy. Common causes: vendor price increases, partial shipments, data entry errors.

---

### 10. `invoice_context`

**What it does:** Returns the full three-way match context for a specific invoice — the invoice itself, the linked PO (with materials), goods receipts, vendor, and payments.

**When to use:** When investigating why a specific invoice is blocked or has a variance.

**Example questions:**
- "What's wrong with INV-000001?"
- "Show me the context for INV-000002"
- "Why is invoice INV-000001 blocked?"

**What you get back:**
- **Invoice**: Date, amounts (gross, tax, net), match status, payment due date, payment block flag, block reason
- **Vendor**: Who sent the invoice
- **Linked PO**: What was ordered (materials, quantities, prices)
- **Goods receipts**: What was actually received
- **Payments**: Any payments already made

**Procurement context:** For example, INV-000001 from VND-MOLEX-SG has status PRICE_VARIANCE and payment_block=TRUE. Comparing the PO price vs. invoice amount reveals the discrepancy. The AP team needs to decide whether to accept the new price, dispute it, or negotiate.

---

### 11. `plant_materials`

**What it does:** Lists all materials sourced at a specific manufacturing plant.

**When to use:** When analyzing a plant's supply base or planning for a plant-specific initiative.

**Example questions:**
- "What materials are sourced at SG01?"
- "Show materials for the Penang plant"

**What you get back:** Materials with their vendor assignments at that plant.

**Procurement context:** Each plant (SG01 = Singapore HQ, MY01 = Penang Production, VN01 = Ho Chi Minh Sub-Assembly) sources different materials based on what it manufactures. The Singapore plant handles pilot assembly and engineering, Penang handles main production, and Vietnam does harness sub-assembly.

---

### 12. `vendor_pos`

**What it does:** Lists all purchase orders placed with a specific vendor.

**When to use:** When reviewing order history with a vendor — frequency, volumes, recent activity.

**Example questions:**
- "Show me all POs for VND-HOKUYO"
- "What have we ordered from CATL?"

**What you get back:** POs with dates, values, statuses, and maverick flags.

---

### 13. `category_tree`

**What it does:** Shows a material category's hierarchy (parent and children) and all materials in that category and its subcategories.

**When to use:** When exploring the procurement taxonomy — understanding how materials are classified.

**Example questions:**
- "Show me the ELEC category tree"
- "What's in the Power category?"

**What you get back:**
- **Category**: Name, level (1 = top-level)
- **Subcategories**: Children in the hierarchy (e.g., ELEC → ELEC-SENS, ELEC-CTRL, ELEC-COMM)
- **Materials**: All materials classified under this category and its children

**Procurement context:** The **category hierarchy** is how organizations group materials for reporting, sourcing strategy, and spend analysis. Top-level categories in this dataset: ELEC (Electronics), MOTN (Motion/Mechanical), POWR (Power), MECH (Mechanical Raw), PACK (Packaging), SRVC (Services), MRO (Maintenance/Repair/Operations).

---

### 14. `vendor_plant_contracts`

**What it does:** Multi-hop query — finds all vendors supplying materials at a plant, then retrieves their contracts.

**When to use:** When assessing contractual coverage at a specific plant. Are all vendors at this plant covered by contracts?

**Example questions:**
- "Show me vendors at SG01 with their contracts"
- "Which Penang plant vendors have contracts?"

**What you get back:** Vendors grouped with their contracts (type, status, validity).

**Procurement context:** This is a compliance question. If a vendor at a plant has no active contract, purchases from them are likely maverick/spot buys at non-negotiated prices.

---

### 15. `search`

**What it does:** Free-text search across all entity names and IDs.

**When to use:** When you don't know the exact entity ID but know a name or keyword.

**Example questions:**
- "Search for Nidec"
- "Find battery"
- "Look up LiDAR"

**What you get back:** Up to 20 matching entities with their type, label, and ID.

---

### 16. `summary`

**What it does:** Returns an overview of the entire knowledge graph — counts of each entity type and relationship type.

**When to use:** When you want to understand the scope of the dataset.

**Example questions:**
- "Give me a summary of the data"
- "How many vendors do we have?"
- "Overview of the knowledge graph"

**What you get back:** Vertex counts (e.g., 120 vendors, 800 materials, 400 POs) and edge counts (e.g., 1200 SUPPLIES edges, 400 ORDERED_FROM edges).

---

## Part 2: Relational Query Patterns (6)

These patterns perform aggregation and filtering on the base tables — SQL-style operations rather than graph traversals. They answer analytical questions that require grouping, summing, or ranking.

---

### 17. `spend_by_vendor`

**What it does:** Ranks vendors by total PO spend (sum of all purchase order values).

**When to use:** Spend analysis — identifying your highest-value vendor relationships.

**Example questions:**
- "Who are our top vendors by spend?"
- "Show me vendor spend ranking"
- "Which vendors get the most business?"

**What you get back:** Top 10 vendors ranked by total spend, with PO count:
```
1. CATL Energy Co., Ltd. (VND-CATL)
   Spend: $234,567 | Count: 42
2. Nidec Corporation (VND-NIDEC-JP)
   Spend: $198,432 | Count: 38
...
```

**Procurement context:** Spend analysis is foundational to strategic sourcing. The Pareto principle often applies — a small number of vendors account for a large share of total spend. These are your strategic vendors that warrant dedicated relationship management.

---

### 18. `spend_by_category`

**What it does:** Aggregates spend by material category.

**When to use:** Understanding where the organization's money goes by product group.

**Example questions:**
- "What's our spend by category?"
- "Show me spend breakdown by material group"

**What you get back:** Categories ranked by total line-item spend:
```
1. Electronics (ELEC)
   Spend: $456,789 | Items: 320
2. Power (POWR)
   Spend: $234,567 | Items: 180
...
```

**Procurement context:** Category spend analysis helps identify sourcing opportunities. If one category dominates spend, it may benefit from a dedicated sourcing strategy, volume discounts, or additional vendor competition.

---

### 19. `po_filter`

**What it does:** Filters purchase orders by status, maverick flag, and/or value range.

**When to use:** Compliance auditing (find maverick POs), financial review (high-value POs), or operational checks (open POs).

**Example questions:**
- "Show me all maverick POs"
- "Find purchase orders over $50,000"
- "Show open POs"

**What you get back:** Filtered list of POs with vendor name, value, status, and maverick flag.

**Procurement context:** **Maverick purchasing** is when buyers create POs outside approved contracts and processes — often at higher prices, without proper approvals, or from non-preferred vendors. Identifying and reducing maverick spend is a key procurement KPI, typically targeting less than 5-8% of total POs.

---

### 20. `invoice_aging`

**What it does:** Groups invoices by match status and shows count and total amount for each.

**When to use:** Accounts payable health check — how many invoices are matched vs. stuck in exceptions?

**Example questions:**
- "What's our invoice aging?"
- "Show me invoice match status breakdown"

**What you get back:**
```
- FULL_MATCH: 245 invoices, total $1,234,567
- PRICE_VARIANCE: 42 invoices, total $234,567
- QUANTITY_VARIANCE: 18 invoices, total $98,432
- BOTH_VARIANCE: 8 invoices, total $45,678
```

**Procurement context:** A healthy AP process has most invoices at FULL_MATCH. A high proportion of variances indicates problems: vendor price increases not reflected in POs, receiving errors, or contract compliance issues. Each unmatched invoice requires manual investigation, which costs time and delays vendor payments.

---

### 21. `overdue_invoices`

**What it does:** Finds invoices where the payment due date has passed and the invoice is not yet paid.

**When to use:** Cash management and vendor relationship health — overdue payments damage vendor trust and may trigger penalties.

**Example questions:**
- "Which invoices are overdue?"
- "Show me past-due invoices"

**What you get back:** Invoices sorted by due date (oldest first) with vendor name, amounts, and match status.

**Procurement context:** Payment terms (e.g., Net 30, Net 60) define when payment is due after invoice receipt. Overdue invoices may be blocked due to match issues, or they may indicate a process bottleneck. Late payments can result in: penalty charges, vendor credit holds (vendor stops shipping), damaged supplier relationships, and missed early-payment discounts.

---

### 22. `vendor_risk`

**What it does:** Lists vendors with risk scores above a threshold, along with their quality and delivery metrics.

**When to use:** Supply chain risk management — proactively identifying and monitoring at-risk vendors.

**Example questions:**
- "Show me high-risk vendors"
- "Which vendors have risk issues?"
- "Vendor risk assessment"

**What you get back:** Vendors sorted by risk score (highest first):
```
- Vendor X (VND-XXX)
  Risk: 85 | Quality: 62 | On-Time: 71% | ESG: 45
- Vendor Y (VND-YYY)
  Risk: 78 | Quality: 68 | On-Time: 75% | ESG: 52
```

**Procurement context:** Vendor risk scoring combines multiple signals:
- **Quality score** — defect rates, rejection rates from goods receipt inspections
- **On-time delivery** — percentage of deliveries arriving by the requested date
- **ESG score** — environmental, social, and governance compliance
- **Financial stability** — not captured in this dataset but typically part of risk models

High-risk vendors supplying critical materials are the top priority. If your sole source for a HIGH-criticality material has a risk score of 85, that's an actionable supply chain risk.

---

## Pattern Coverage Summary

| # | Pattern | Type | Needs Entity ID | Example Question |
|---|---------|------|-----------------|------------------|
| 1 | `entity_lookup` | Graph | Yes | "What is GR-000001?" |
| 2 | `vendor_profile` | Graph | Yes | "Tell me about VND-HOKUYO" |
| 3 | `vendor_materials` | Graph | Yes | "What does VND-CATL supply?" |
| 4 | `material_vendors` | Graph | Yes | "Who supplies MAT-LIDAR-2D?" |
| 5 | `po_details` | Graph | Yes | "Show me PO-000001" |
| 6 | `p2p_chain` | Graph | Yes | "P2P chain for PO-000001" |
| 7 | `contract_pos` | Graph | Yes | "POs under CTR-00001" |
| 8 | `vendor_contracts` | Graph | Yes | "Contracts for VND-HOKUYO" |
| 9 | `invoice_issues` | Graph | No | "Show invoices with problems" |
| 10 | `invoice_context` | Graph | Yes | "What's wrong with INV-000001?" |
| 11 | `plant_materials` | Graph | Yes | "Materials at SG01" |
| 12 | `vendor_pos` | Graph | Yes | "POs for VND-CATL" |
| 13 | `category_tree` | Graph | Yes | "Show the ELEC category" |
| 14 | `vendor_plant_contracts` | Graph | Yes | "Vendors at SG01 with contracts" |
| 15 | `search` | Graph | No | "Search for Nidec" |
| 16 | `summary` | Graph | No | "Give me a summary" |
| 17 | `spend_by_vendor` | Relational | No | "Top vendors by spend" |
| 18 | `spend_by_category` | Relational | No | "Spend by category" |
| 19 | `po_filter` | Relational | No | "Show maverick POs" |
| 20 | `invoice_aging` | Relational | No | "Invoice aging summary" |
| 21 | `overdue_invoices` | Relational | No | "Overdue invoices" |
| 22 | `vendor_risk` | Relational | No | "High-risk vendors" |

**Note:** Patterns that require an entity ID but don't receive one will return "No [entity] found." The system does not currently prompt the user to provide a missing ID — this is a known limitation that will be addressed in the agentic phase.
