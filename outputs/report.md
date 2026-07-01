# NimbusAI — GPU Cost Optimization Report

**Period:** monthly  
**Baseline spend:** $27,133  
**Optimized spend:** $14,639  
**Projected savings:** $12,494  (**46%**)

## Savings by lever

| Lever | Savings (USD) |
|---|---|
| Inference (cascade/cache/batch) | $1,199 |
| Purchasing (spot/reserved) | $10,040 |
| Right-size util-lies | $655 |
| Kill idle GPUs | $600 |

## Sustainability

- Energy per query: 0.24 Wh
- Carbon per query: 0.091 gCO2e
- Cheapest+cleanest region: europe-north1

## Extension: Cache Economics

- Cached read tokens: 1,703,990
- Cache write cost: $0.42/day
- Net cache savings: $0.76/day
- small: 0.32 avg reads vs 0.11 break-even -> worth it: True
- large: 0.32 avg reads vs 0.11 break-even -> worth it: True

## Extension: Reasoning Budget

- Reasoning requests: 201 (8.4% of traffic)
- Reasoning token share: 16.5%
- Reasoning cost share: 15.7%
- Reasoning energy share: 94.0%
- Rule: cap reasoning near 10% of tokens unless task complexity or confidence requires escalation.

## Extension: Carbon-Aware Scheduling

- Move interruptible jobs from us-east-1 to europe-north1.
- Avoided carbon: 1,479.5 kgCO2e/month
- Electricity savings: $126.81/month

_Figures are June-2026 as-of snapshots; re-baseline before acting._