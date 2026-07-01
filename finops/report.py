"""Report assembly — the lab's deliverable: baseline vs optimized + savings chart."""
from __future__ import annotations


def build_report(baseline_usd: float, optimized_usd: float, levers: dict,
                 sustainability: dict | None = None, period: str = "monthly",
                 extensions: dict | None = None) -> str:
    """Return a markdown cost-optimization report."""
    savings = baseline_usd - optimized_usd
    pct = (savings / baseline_usd * 100.0) if baseline_usd > 0 else 0.0
    lines = [
        "# NimbusAI — GPU Cost Optimization Report",
        "",
        f"**Period:** {period}  ",
        f"**Baseline spend:** ${baseline_usd:,.0f}  ",
        f"**Optimized spend:** ${optimized_usd:,.0f}  ",
        f"**Projected savings:** ${savings:,.0f}  (**{pct:.0f}%**)",
        "",
        "## Savings by lever",
        "",
        "| Lever | Savings (USD) |",
        "|---|---|",
    ]
    for name, amount in levers.items():
        lines.append(f"| {name} | ${amount:,.0f} |")
    if sustainability:
        lines += [
            "",
            "## Sustainability",
            "",
            f"- Energy per query: {sustainability.get('wh_per_query', 0):.2f} Wh",
            f"- Carbon per query: {sustainability.get('carbon_g', 0):.3f} gCO2e",
            f"- Cheapest+cleanest region: {sustainability.get('best_region', 'n/a')}",
        ]
    if extensions:
        cache = extensions.get("cache")
        if cache:
            lines += [
                "",
                "## Extension: Cache Economics",
                "",
                f"- Cached read tokens: {cache.get('cached_read_tokens', 0):,}",
                f"- Cache write cost: ${cache.get('write_cost_daily', 0):,.2f}/day",
                f"- Net cache savings: ${cache.get('net_savings_daily', 0):,.2f}/day",
            ]
            for tier, stats in cache.get("break_even", {}).items():
                policy = cache.get("policy", {}).get(tier)
                lines.append(
                    f"- {tier}: {stats.get('avg_reads', 0):.2f} avg reads vs "
                    f"{stats.get('break_even_reads', 0):.2f} break-even -> worth it: {policy}"
                )
        reasoning = extensions.get("reasoning")
        if reasoning:
            lines += [
                "",
                "## Extension: Reasoning Budget",
                "",
                f"- Reasoning requests: {reasoning.get('requests', 0):,} "
                f"({reasoning.get('request_share', 0):.1%} of traffic)",
                f"- Reasoning token share: {reasoning.get('token_share', 0):.1%}",
                f"- Reasoning cost share: {reasoning.get('cost_share', 0):.1%}",
                f"- Reasoning energy share: {reasoning.get('energy_share', 0):.1%}",
                f"- Rule: cap reasoning near {reasoning.get('cap_target_token_share', 0):.0%} of tokens "
                "unless task complexity or confidence requires escalation.",
            ]
        carbon = extensions.get("carbon_schedule")
        if carbon:
            lines += [
                "",
                "## Extension: Carbon-Aware Scheduling",
                "",
                f"- Move interruptible jobs from {carbon.get('current_region', 'n/a')} "
                f"to {carbon.get('best_region', 'n/a')}.",
                f"- Avoided carbon: {carbon.get('carbon_saved_g', 0) / 1000:,.1f} kgCO2e/month",
                f"- Electricity savings: ${carbon.get('energy_cost_saved', 0):,.2f}/month",
            ]
    lines += ["", "_Figures are June-2026 as-of snapshots; re-baseline before acting._"]
    return "\n".join(lines)


def savings_waterfall(levers: dict, path: str) -> str:
    """Write a simple savings bar chart PNG. Returns the path."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        names = list(levers.keys())
        vals = [levers[n] for n in names]
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.bar(names, vals, color="#2e548a")
        ax.set_ylabel("Savings (USD / month)")
        ax.set_title("GPU cost savings by FinOps lever")
        plt.xticks(rotation=20, ha="right")
        plt.tight_layout()
        fig.savefig(path, dpi=110)
        plt.close(fig)
        return path
    except Exception:
        pass

    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return ""
    width, height = 1000, 560
    margin_l, margin_r, margin_t, margin_b = 90, 30, 70, 150
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    title = "GPU cost savings by FinOps lever"
    draw.text((margin_l, 24), title, fill=(30, 30, 30), font=font)
    vals = [max(0, float(v)) for v in levers.values()]
    max_val = max(vals) if vals else 1.0
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b
    draw.line((margin_l, margin_t, margin_l, margin_t + plot_h), fill=(40, 40, 40), width=2)
    draw.line((margin_l, margin_t + plot_h, width - margin_r, margin_t + plot_h), fill=(40, 40, 40), width=2)
    bar_gap = 28
    bar_w = max(28, int((plot_w - bar_gap * (len(vals) + 1)) / max(1, len(vals))))
    for i, (name, raw_val) in enumerate(levers.items()):
        val = max(0, float(raw_val))
        x0 = margin_l + bar_gap + i * (bar_w + bar_gap)
        x1 = x0 + bar_w
        bar_h = int((val / max_val) * (plot_h - 20)) if max_val else 0
        y0 = margin_t + plot_h - bar_h
        y1 = margin_t + plot_h
        draw.rectangle((x0, y0, x1, y1), fill=(46, 84, 138))
        draw.text((x0, max(margin_t, y0 - 18)), f"${val:,.0f}", fill=(20, 20, 20), font=font)
        words = name.replace("(", "").replace(")", "").split()
        label_lines = []
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if len(candidate) > 16:
                label_lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            label_lines.append(line)
        for j, line in enumerate(label_lines[:4]):
            draw.text((x0, y1 + 10 + j * 14), line, fill=(30, 30, 30), font=font)
    draw.text((12, margin_t + plot_h // 2), "Savings USD / month", fill=(30, 30, 30), font=font)
    img.save(path)
    return path
