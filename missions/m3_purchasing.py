"""M3 — Purchasing Strategy: break-even, tier choice, spot-checkpoint sim (deck §4).

Run: python missions/m3_purchasing.py
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num, catalog_by_type
from finops import pricing, sustainability

DAYS = 30


def run(verbose: bool = True) -> dict:
    jobs = load_csv("workloads.csv")
    cat = catalog_by_type()
    on_demand_monthly = optimized_monthly = 0.0
    recs = []
    carbon_recs = []
    current_region = "us-east-1"
    best_region = min(
        sustainability.REGION_CARBON,
        key=lambda r: (sustainability.REGION_CARBON[r], sustainability.REGION_PRICE_KWH.get(r, 999)),
    )
    for j in jobs:
        gtype = j["gpu_type"]
        ngpu = int(num(j["num_gpus"]))
        hpd = num(j["hours_per_day"])
        interruptible = bool(int(num(j["interruptible"])))
        c = cat[gtype]
        gpu_hours = hpd * DAYS * ngpu
        od = num(c["on_demand_hr"])
        on_demand_cost = gpu_hours * od

        tier = pricing.recommend_tier(hpd, interruptible)
        if tier == "spot":
            sim = pricing.spot_checkpoint_cost(gpu_hours, num(c["spot_hr"]), od)
            opt_cost = sim["spot_cost"]
        elif tier == "reserved":
            opt_cost = gpu_hours * num(c["reserved_3yr_hr"])
        else:
            opt_cost = on_demand_cost

        on_demand_monthly += on_demand_cost
        optimized_monthly += opt_cost
        recs.append({"job_id": j["job_id"], "gpu_type": gtype, "tier": tier,
                     "on_demand": round(on_demand_cost), "optimized": round(opt_cost)})

        if interruptible:
            wh = gpu_hours * num(c["watts"])
            current_carbon = sustainability.carbon_g(wh, current_region)
            best_carbon = sustainability.carbon_g(wh, best_region)
            current_energy_cost = sustainability.energy_cost_usd(wh, current_region)
            best_energy_cost = sustainability.energy_cost_usd(wh, best_region)
            carbon_recs.append({
                "job_id": j["job_id"],
                "gpu_type": gtype,
                "energy_kwh": round(wh / 1000.0, 1),
                "current_region": current_region,
                "best_region": best_region,
                "current_carbon_g": round(current_carbon),
                "best_carbon_g": round(best_carbon),
                "carbon_saved_g": round(current_carbon - best_carbon),
                "energy_cost_saved": round(current_energy_cost - best_energy_cost, 2),
            })

    savings = on_demand_monthly - optimized_monthly
    savings_pct = savings / on_demand_monthly * 100 if on_demand_monthly else 0.0

    if verbose:
        print("== M3 Purchasing Strategy ==")
        print(f"break-even utilization @ 45% reserved discount = {pricing.break_even_utilization(0.45):.0%}")
        print(f"{'job':18}{'gpu':7}{'tier':11}{'on-demand':>12}{'optimized':>12}")
        for r in recs:
            print(f"{r['job_id']:18}{r['gpu_type']:7}{r['tier']:11}${r['on_demand']:>11,}${r['optimized']:>11,}")
        print(f"\nmonthly: on-demand ${on_demand_monthly:,.0f} -> optimized ${optimized_monthly:,.0f}  ({savings_pct:.1f}% saved)")
        if carbon_recs:
            total_saved = sum(r["carbon_saved_g"] for r in carbon_recs)
            print("\ncarbon-aware scheduling for interruptible jobs:")
            print(f"  move {current_region} -> {best_region}: {total_saved/1000:,.1f} kgCO2e avoided/month")
            for r in carbon_recs:
                print(f"  {r['job_id']:18}{r['energy_kwh']:>8,.1f} kWh  {r['carbon_saved_g']/1000:>8,.1f} kgCO2e saved")

    return {"recommendations": recs, "on_demand_monthly": round(on_demand_monthly),
            "optimized_monthly": round(optimized_monthly), "savings_pct": round(savings_pct, 1),
            "carbon_schedule": {
                "current_region": current_region,
                "best_region": best_region,
                "jobs": carbon_recs,
                "carbon_saved_g": round(sum(r["carbon_saved_g"] for r in carbon_recs)),
                "energy_cost_saved": round(sum(r["energy_cost_saved"] for r in carbon_recs), 2),
            }}


if __name__ == "__main__":
    run()
