# Plan: Phase 1 — Configurable ML Signal Enrichment (UC-02 Invoice Match)

## Context

The generated procurement data has trivially separable ML signals — a single-feature threshold achieves ~95% accuracy for every Tier 1 use case. We need to enrich the data generation so ML models require multi-feature reasoning.

**Scope**: Phase 1 only — enrichments 1a (vendor score correlations) and 1b (invoice variance ~ vendor quality). All ML noise parameters are **configurable** via `seeds/config.yaml` so the signal difficulty can be tuned without code changes.

**Best first use case**: UC-02 (Invoice Three-Way Match) — highest positive rate (15-20%), clean multi-class label (`match_status`), works at 1x scale (320 invoices), and the key enrichment is a single-file change.

## Files Modified

| Action | File | Change |
|--------|------|--------|
| Edit | `src/procurement_generator/config.py` | Added `MLSignalConfig` dataclass, loaded from YAML |
| Edit | `seeds/config.yaml` | Added `ml_signal` section with tunable parameters |
| Edit | `src/procurement_generator/generators/vendors.py` | 1a: Correlated vendor scores using config params |
| Edit | `src/procurement_generator/generators/invoices.py` | 1b: Invoice variance driven by vendor quality using config params |

## Changes

### 1. `MLSignalConfig` dataclass (`config.py`)

```python
@dataclass
class MLSignalConfig:
    enabled: bool = False
    vendor_score_correlation: float = 0.7
    vendor_score_noise_std: float = 10.0
    invoice_quality_influence: float = 0.5
    invoice_base_match_rate: float = 0.82
    invoice_variance_scale: float = 0.08
```

Added as a field on `ScaleConfig` with `default_factory=MLSignalConfig`. Loaded from `ml_signal` section in `config.yaml`.

### 2. Vendor score correlations (`vendors.py`)

When `ml_signal.enabled`, risk score is a blend of correlated component (`100 - quality + noise`) and independent random draw, controlled by `vendor_score_correlation` (0.0 = independent, 1.0 = perfectly correlated).

### 3. Invoice variance by vendor quality (`invoices.py`)

When `ml_signal.enabled`:
- Match rate adjusted per vendor: `base * (1 - influence * (1 - quality/100))`
- Price variance magnitude scaled by vendor quality via `invoice_variance_scale`
- Variance type distribution preserved (55% price / 28% quantity / 17% both)

### 4. Backward compatibility

Setting `ml_signal.enabled: false` reproduces the original independent-score, fixed-82%-match behavior exactly.
