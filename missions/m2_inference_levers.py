"""M2 - Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num
from finops import pricing, sustainability

# $/1M tokens (input, output), illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}
CACHE_WRITE_COST_PER_M = {"small": 0.02, "large": 0.30}


def _row_cost(r: dict, route_tier: str, cached_in: int = 0, batch: bool = False) -> float:
    pin, pout = MODEL_PRICES[route_tier]
    return pricing.request_cost(
        int(num(r["input_tokens"])),
        int(num(r["output_tokens"])),
        pin,
        pout,
        cached_in=cached_in,
        batch=batch,
    )


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    base_cost = opt_cost = 0.0
    no_cache_opt_cost = 0.0
    total_tokens = 0
    cached_read_tokens = 0
    cacheable_input_tokens = 0
    cache_write_cost = 0.0
    reasoning_cost = non_reasoning_cost = 0.0
    reasoning_tokens = non_reasoning_tokens = 0
    reasoning_energy_wh = non_reasoning_energy_wh = 0.0

    by_tier_cacheable = {tier: 0 for tier in MODEL_PRICES}
    by_tier_cached_reads = {tier: 0 for tier in MODEL_PRICES}
    for r in rows:
        cached = int(num(r["cached_input_tokens"]))
        if cached > 0:
            tier = r["route_tier"]
            by_tier_cached_reads[tier] += cached
            by_tier_cacheable[tier] += int(num(r["input_tokens"]))

    cache_policy = {}
    cache_break_even = {}
    for tier, (pin, _) in MODEL_PRICES.items():
        avg_reads = by_tier_cached_reads[tier] / by_tier_cacheable[tier] if by_tier_cacheable[tier] else 0.0
        be_reads = pricing.cache_break_even_reads(CACHE_WRITE_COST_PER_M[tier], read_price_per_m=pin)
        cache_policy[tier] = pricing.cache_is_worth_it(avg_reads, CACHE_WRITE_COST_PER_M[tier], read_price_per_m=pin)
        cache_break_even[tier] = {"avg_reads": avg_reads, "break_even_reads": be_reads}

    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"]))
        is_batch = bool(int(num(r["is_batch"])))
        is_reasoning = bool(int(num(r["is_reasoning"])))
        total_tokens += inp + out

        # BASELINE: everything on the large model, no cache, no batch.
        lin, lout = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, lin, lout)

        # OPTIMIZED: cascade, prompt caching when it clears break-even, and batch API.
        tier = r["route_tier"]
        effective_cached = cached if cache_policy[tier] else 0
        row_cost = _row_cost(r, tier, cached_in=effective_cached, batch=is_batch)
        opt_cost += row_cost
        no_cache_opt_cost += _row_cost(r, tier, cached_in=0, batch=is_batch)
        if effective_cached:
            cached_read_tokens += effective_cached
            cacheable_input_tokens += inp
            cache_write_cost += (inp / 1e6) * CACHE_WRITE_COST_PER_M[tier]

        row_tokens = inp + out
        row_wh = sustainability.wh_per_query(row_tokens, is_reasoning=is_reasoning)
        if is_reasoning:
            reasoning_cost += row_cost
            reasoning_tokens += row_tokens
            reasoning_energy_wh += row_wh
        else:
            non_reasoning_cost += row_cost
            non_reasoning_tokens += row_tokens
            non_reasoning_energy_wh += row_wh

    opt_cost += cache_write_cost
    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0
    cache_savings = max(0.0, no_cache_opt_cost - (opt_cost - cache_write_cost) - cache_write_cost)
    reasoning_requests = sum(1 for r in rows if int(num(r["is_reasoning"])))
    current_reasoning_share = reasoning_tokens / total_tokens if total_tokens else 0.0
    cap_target = 0.10
    avoidable_share = max(0.0, current_reasoning_share - cap_target)
    cap_energy_savings_wh = reasoning_energy_wh * (avoidable_share / current_reasoning_share) if current_reasoning_share else 0.0

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")
        print("\ncache economics:")
        for tier, stats in cache_break_even.items():
            print(f"  {tier:5} avg reads {stats['avg_reads']:.2f} vs break-even {stats['break_even_reads']:.2f} -> worth it? {cache_policy[tier]}")
        print(f"  cache net savings: ${cache_savings:,.2f}/day after ${cache_write_cost:,.2f}/day write cost")
        print("\nreasoning budget:")
        print(f"  reasoning requests: {reasoning_requests}/{len(rows)} ({reasoning_requests/len(rows):.1%})")
        print(f"  reasoning cost share: {reasoning_cost/opt_cost:.1%}; token share: {current_reasoning_share:.1%}")
        print(f"  reasoning energy share: {reasoning_energy_wh/(reasoning_energy_wh + non_reasoning_energy_wh):.1%}")

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        "cache": {
            "cached_read_tokens": int(cached_read_tokens),
            "cacheable_input_tokens": int(cacheable_input_tokens),
            "write_cost_daily": round(cache_write_cost, 4),
            "net_savings_daily": round(cache_savings, 4),
            "policy": cache_policy,
            "break_even": {k: {kk: round(vv, 3) for kk, vv in v.items()} for k, v in cache_break_even.items()},
        },
        "reasoning": {
            "requests": reasoning_requests,
            "request_share": round(reasoning_requests / len(rows), 4),
            "token_share": round(current_reasoning_share, 4),
            "cost_daily": round(reasoning_cost, 4),
            "cost_share": round(reasoning_cost / opt_cost, 4) if opt_cost else 0.0,
            "energy_wh": round(reasoning_energy_wh, 2),
            "energy_share": round(reasoning_energy_wh / (reasoning_energy_wh + non_reasoning_energy_wh), 4)
            if (reasoning_energy_wh + non_reasoning_energy_wh) else 0.0,
            "cap_target_token_share": cap_target,
            "cap_energy_savings_wh": round(cap_energy_savings_wh, 2),
        },
    }


if __name__ == "__main__":
    run()
