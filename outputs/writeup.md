# NimbusAI GPU FinOps Write-up

## 1. Baseline vs Optimized

Baseline monthly spend is $27,133. Optimized monthly spend is $14,639. The plan saves $12,494/month, or 46%.

Inference unit economics improve from $6.488/1M-token to $1.182/1M-token after cascade routing, prompt caching, batch API, and cache write-cost gating. Total inference savings are $1,199/month.

## 2. Savings Levers

| Lever | Monthly savings | Why it matters |
|---|---:|---|
| Purchasing (spot/reserved) | $10,040 | Largest lever because long-running inference jobs move to reserved pricing and interruptible training/eval jobs move to spot with checkpoint overhead included. |
| Inference cascade/cache/batch | $1,199 | Measures cost per token, not GPU-hours. Small-model routing, batch discount, and cached reads reduce the served-token bill. |
| Right-size util-lies | $655 | High GPU-Util with low MFU means the workload keeps the GPU busy without using proportional FLOPs. |
| Kill idle GPUs | $600 | Idle hours are pure waste and should be automated away first. |

## 3. GPU-Util Lie

The lab flags `gpu-h100-4` as the headline GPU-Util lie: GPU-Util is near 98%, but MFU is only about 0.20. This happens because GPU-Util mostly says the device clock is active; it does not prove the model is using the rented FLOPs efficiently. Memory stalls, small batches, synchronization, or kernel overhead can keep the GPU "busy" while useful compute remains low.

Financial impact: the right-sizing lever estimates $655/month of savings from moving util-lie workloads down one GPU tier, and idle cleanup adds another $600/month.

## 4. Extensions Completed

### Extension A: Cache Economics

Implemented `cache_break_even_reads()` and `cache_is_worth_it()` in `finops/pricing.py`, then applied the policy in M2 before counting cached-read savings.

Measured result:

- Cached read tokens: 1,703,990/day
- Cache write cost: $0.42/day
- Net cache savings after write cost: $0.76/day
- Small tier: 0.32 estimated average reads vs 0.11 break-even
- Large tier: 0.32 estimated average reads vs 0.11 break-even

Insight: caching is worth it for this dataset, but not unconditionally. If reuse drops below break-even, cached tokens should be billed as normal uncached input.

### Extension B: Reasoning Budget

M2 now separates reasoning traffic cost and energy from normal traffic.

Measured result:

- Reasoning requests: 201 of 2,400, or 8.4% of traffic
- Reasoning token share: 16.5%
- Reasoning cost share: 15.7%
- Reasoning energy share: 94.0%

Recommended rule: cap reasoning near 10% of tokens unless task complexity or low confidence requires escalation. This protects energy budget while preserving reasoning for high-value cases.

### Extension C: Carbon-Aware Scheduling

M3 now evaluates interruptible jobs for regional carbon scheduling. The policy moves interruptible jobs from `us-east-1` to `europe-north1`, the cleanest region in the lab catalog.

Measured result:

- Avoided carbon: 1,479.5 kgCO2e/month
- Electricity savings: $126.81/month

Insight: the cleanest region is not always the absolute cheapest, but here it also reduces power cost versus `us-east-1`. This is a good default for batch, training, and evaluation jobs that are not latency-sensitive.

## 5. Recommendations for NimbusAI

1. Move interruptible training/eval jobs to spot with checkpointing, and reserve steady 24/7 inference workloads only after utilization clears break-even.
2. Govern inference in `$/1M-token`: use cascade routing by default, batch async requests, and enable prompt caching only when reuse beats write-cost break-even.
3. Add operational guardrails: auto-shutdown idle GPUs, monitor MFU/MBU instead of relying on GPU-Util, and cap reasoning traffic by task complexity or confidence.
