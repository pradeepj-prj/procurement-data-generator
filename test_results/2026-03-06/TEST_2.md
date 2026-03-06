# Test Results: Phase 1 ML Signal Enrichment

**Date**: 2026-03-06
**Config**: `ml_signal.enabled: true`, default parameters

## Pipeline Result

```
FATAL checks:   78 passed, 0 failed
WARNING checks: 8 passed, 0 warnings
```

All 12 seeds verified. Total rows: 10,582.

## Row Counts (identical to TEST_1)

| Table | Count |
|-------|-------|
| material_master | 800 |
| vendor_master | 120 |
| contract_header | 40 |
| pr_header | 500 |
| po_header | 400 |
| gr_header | 350 |
| invoice_header | 320 |
| payment | 245 |
| **TOTAL** | **10,582** |

## Signal Validation

### 1a: Vendor Quality-Risk Correlation

```
Pearson correlation: -0.575 (previously ~0.0 with independent draws)
```

High-quality vendors (95) get lower risk scores (~15-25); low-quality vendors (60) get higher risk (~55-70). Models must now use both features.

### 1b: Invoice Match Rate by Vendor Quality Quartile

| Quartile | Count | Full Match Rate |
|----------|-------|----------------|
| Q1 (40-64) | 20 | 60.0% |
| Q2 (65-74) | 82 | 72.0% |
| Q3 (75-84) | 55 | 74.5% |
| Q4 (85-98) | 163 | 81.6% |

Overall full-match rate: 77% (within 70-95% validation window). Clear gradient from 60% → 82% across quality quartiles.

### Statistical Validators

| Check | Result |
|-------|--------|
| Invoice full-match rate | 77% (window: 70-95%) — PASS |
| Maverick PO % | 6% (window: 2-12%) — PASS |
| On-contract PO line % | 73% (window: 60-85%) — PASS |

## Backward Compatibility

Verified: setting `ml_signal.enabled: false` restores independent vendor scores and fixed 82% match rate distribution.
