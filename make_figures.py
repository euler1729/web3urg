"""Render the result figures (vector PDF, IEEE column width).

Reads the CSVs produced by run_experiments.py and writes four figures to
simulation/figures/ and to manuscript/pdf/ so the LaTeX source can
include them directly:

  fig3_latency_ecdf.pdf          E1  platform operation latency ECDFs
  fig4_nft_mint.pdf              E2  NFT mint confirmation time + cost
  fig5_scalability.pdf           E3  response time / success vs. users
  fig6_notarization_storage.pdf  E5  notarization cost + storage growth
"""

import csv
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config as C

# validated reference palette (light mode) — fixed slot order
BLUE, AQUA, YELLOW, GREEN, VIOLET = "#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7"
BLUE_DARK = "#184f95"
INK, INK2, MUTED, GRID, BASE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 7.5,
    "axes.labelsize": 7.5,
    "axes.titlesize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "axes.edgecolor": BASE,
    "axes.linewidth": 0.7,
    "axes.labelcolor": INK2,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.5,
    "axes.axisbelow": True,
    "legend.frameon": False,
    "pdf.fonttype": 42,
})

COL_W = 3.45  # IEEE single-column width in inches


def read_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def save(fig, name):
    fig.tight_layout(pad=0.4)
    for d in (C.FIGURES_DIR, C.MANUSCRIPT_PDF_DIR):
        d.mkdir(exist_ok=True, parents=True)
        fig.savefig(d / name, bbox_inches="tight")
    # PNG preview alongside the vector PDF, for GitHub/README rendering
    fig.savefig(C.FIGURES_DIR / name.replace(".pdf", ".png"), bbox_inches="tight", dpi=200)
    plt.close(fig)
    print(f"wrote {name}")


# ---------------------------------------------------------------- figure 3
def fig_latency():
    rows = read_csv(C.RESULTS_DIR / "platform_latency.csv")
    ops = [
        ("recordSensorBatch", "Sensor batch write", BLUE),
        ("redeemToken", "Token redemption", AQUA),
        ("registerPlot", "Plot registration", YELLOW),
        ("marketplaceOrder", "Marketplace order", GREEN),
    ]
    fig, ax = plt.subplots(figsize=(COL_W, 2.2))
    for op, label, color in ops:
        v = np.sort([float(r["latency_ms"]) for r in rows if r["operation"] == op])
        ecdf = np.arange(1, len(v) + 1) / len(v)
        ax.plot(v, ecdf, color=color, lw=1.6, label=label)
    ax.axhline(0.95, color=MUTED, lw=0.7, ls=(0, (3, 2)))
    ax.text(238, 0.905, "p95", color=MUTED, fontsize=6.5)
    ax.set_xlim(0, 250)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Operation latency (ms)")
    ax.set_ylabel("Cumulative probability")
    ax.legend(loc="lower right", handlelength=1.4)
    save(fig, "fig3_latency_ecdf.pdf")


# ---------------------------------------------------------------- figure 4
def fig_nft_mint():
    rows = read_csv(C.RESULTS_DIR / "onchain_tx.csv")
    mint = [r for r in rows if r["tx_type"] == "mintHarvestNFT"]
    t = np.array([float(r["confirm_time_s"]) for r in mint])
    cost = np.array([float(r["cost_usd"]) for r in mint]) * 100  # US cents

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(COL_W, 3.0))

    ax1.hist(t, bins=np.arange(0, 20.5, 0.5), color=BLUE, edgecolor="#fcfcfb",
             linewidth=0.4, weights=np.full_like(t, 100.0 / len(t)))
    p95_t = np.percentile(t, 95)
    ax1.axvline(p95_t, color=INK2, lw=0.8, ls=(0, (3, 2)))
    ax1.text(p95_t + 0.3, ax1.get_ylim()[1] * 0.85,
             f"p95 = {p95_t:.1f} s", color=INK2, fontsize=6.5)
    ax1.set_xlim(0, 20)
    ax1.set_xlabel("NFT mint confirmation time (s)")
    ax1.set_ylabel("Share of mints (%)")

    ax2.hist(cost, bins=np.arange(0, 3.05, 0.1), color=AQUA, edgecolor="#fcfcfb",
             linewidth=0.4, weights=np.full_like(cost, 100.0 / len(cost)))
    p95_c = np.percentile(cost, 95)
    ax2.axvline(p95_c, color=INK2, lw=0.8, ls=(0, (3, 2)))
    ax2.text(p95_c + 0.05, ax2.get_ylim()[1] * 0.85,
             f"p95 = {p95_c:.2f} ¢", color=INK2, fontsize=6.5)
    ax2.set_xlim(0, 3)
    ax2.set_xlabel("NFT mint transaction cost (US cents)")
    ax2.set_ylabel("Share of mints (%)")

    save(fig, "fig4_nft_mint.pdf")


# ---------------------------------------------------------------- figure 5
def fig_scalability():
    rows = read_csv(C.RESULTS_DIR / "load_test.csv")
    n = np.array([int(r["concurrent_users"]) for r in rows])
    p50 = np.array([float(r["p50_ms"]) for r in rows])
    p95 = np.array([float(r["p95_ms"]) for r in rows])
    ok = np.array([float(r["success_rate"]) for r in rows]) * 100

    sla = [ni for ni, a, b in zip(n, p95, ok)
           if a <= C.SLA_P95_MS and b >= C.SLA_SUCCESS * 100]
    n_max = max(sla) if sla else None

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(COL_W, 3.2), sharex=True)

    ax1.plot(n, p95, color=BLUE, lw=1.6, marker="o", ms=3, label="p95")
    ax1.plot(n, p50, color="#86b6ef", lw=1.6, marker="o", ms=3, label="p50")
    ax1.axhline(C.SLA_P95_MS, color=MUTED, lw=0.7, ls=(0, (3, 2)))
    ax1.text(120, C.SLA_P95_MS * 1.12, "500 ms SLA", color=MUTED, fontsize=6.5)
    ax1.set_yscale("log")
    ax1.set_ylabel("Response time (ms)")
    ax1.legend(loc="upper left", handlelength=1.4)

    ax2.plot(n, ok, color=GREEN, lw=1.6, marker="o", ms=3, label="Success rate")
    ax2.axhline(C.SLA_SUCCESS * 100, color=MUTED, lw=0.7, ls=(0, (3, 2)))
    ax2.text(120, C.SLA_SUCCESS * 100 - 9, "99.5% SLA", color=MUTED, fontsize=6.5)
    ax2.set_ylim(0, 104)
    ax2.set_xlabel("Concurrent active users")
    ax2.set_ylabel("Success rate (%)")
    ax2.legend(loc="lower left", handlelength=1.4)

    if n_max:
        for ax in (ax1, ax2):
            ax.axvline(n_max, color=VIOLET, lw=0.9, ls=(0, (1, 1.5)))
        ax1.text(n_max + 25, ax1.get_ylim()[0] * 1.4,
                 f"max = {n_max}", color=VIOLET, fontsize=6.5)

    save(fig, "fig5_scalability.pdf")


# ---------------------------------------------------------------- figure 6
def fig_notarization_storage():
    nota = read_csv(C.RESULTS_DIR / "notarization.csv")
    stor = read_csv(C.RESULTS_DIR / "storage_growth.csv")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(COL_W, 3.0))

    labels = []
    for r in nota:
        h = float(r["interval_h"])
        labels.append(f"{int(h * 60)} min" if h < 1 else f"{int(h)} h")
    cost = [float(r["daily_cost_usd"]) for r in nota]
    delay = [float(r["mean_anchor_delay_min"]) for r in nota]
    x = np.arange(len(labels))
    bars = ax1.bar(x, cost, width=0.55, color=BLUE, zorder=3)
    for xi, b, d in zip(x, bars, delay):
        ax1.text(xi, b.get_height() + max(cost) * 0.04,
                 f"delay {d:.0f} min" if d < 60 else f"delay {d/60:.0f} h",
                 ha="center", color=INK2, fontsize=6.3)
    ax1.set_xticks(x, labels)
    ax1.set_ylim(0, max(cost) * 1.25)
    ax1.set_xlabel("Notarization batching interval")
    ax1.set_ylabel("Public-chain cost (USD/day)")
    ax1.grid(axis="x", visible=False)

    wk = [int(r["week"]) for r in stor]
    gb = [float(r["cumulative_gb"]) for r in stor]
    ax2.plot(wk, gb, color=AQUA, lw=1.8)
    ax2.annotate(f"{gb[-1]:.2f} GB", xy=(wk[-1], gb[-1]),
                 xytext=(wk[-1] - 5.5, gb[-1] * 0.92), color=INK2, fontsize=6.5)
    ax2.set_xlim(1, C.SIM_WEEKS)
    ax2.set_ylim(0, max(gb) * 1.15)
    ax2.set_xlabel("Week")
    ax2.set_ylabel("Private ledger size (GB)")

    save(fig, "fig6_notarization_storage.pdf")


# ---------------------------------------------------------------- figure 7
def fig_sensitivity():
    rows = read_csv(C.RESULTS_DIR / "sensitivity.csv")

    def sweep(param, field, scale=1.0):
        pts = [(float(r["value"]), float(r[field]) * scale)
               for r in rows if r["parameter"] == param and r[field]]
        return [p[0] for p in pts], [p[1] for p in pts]

    fig, axes = plt.subplots(2, 2, figsize=(COL_W, 3.4))
    (ax1, ax2), (ax3, ax4) = axes

    # (a) mint cost vs gas price median
    x, mean_c = sweep("GAS_PRICE_MEDIAN_GWEI", "mint_cost_mean_usd", 100)
    _, p95_c = sweep("GAS_PRICE_MEDIAN_GWEI", "mint_cost_p95_usd", 100)
    ax1.plot(x, p95_c, color=BLUE, lw=1.5, marker="o", ms=2.8, label="p95")
    ax1.plot(x, mean_c, color="#86b6ef", lw=1.5, marker="o", ms=2.8, label="mean")
    ax1.axhline(5.0, color=MUTED, lw=0.7, ls=(0, (3, 2)))
    ax1.text(19, 4.45, "5 ¢ target", color=MUTED, fontsize=6)
    ax1.set_ylim(0, 5.6)
    ax1.set_xlabel("Median gas price (gwei)")
    ax1.set_ylabel("Mint cost (¢)")
    ax1.legend(loc="center right", handlelength=1.2)

    # (b) reward delivery success vs congestion frequency
    x, first = sweep("P_SPIKE_HOUR", "reward_first_attempt_success", 100)
    _, final = sweep("P_SPIKE_HOUR", "reward_final_success", 100)
    ax2.plot(x, final, color=GREEN, lw=1.5, marker="o", ms=2.8, label="final")
    ax2.plot(x, first, color=YELLOW, lw=1.5, marker="o", ms=2.8, label="1st try")
    ax2.axhline(99.5, color=MUTED, lw=0.7, ls=(0, (3, 2)))
    ax2.text(0.021, 99.0, "99.5% target", color=MUTED, fontsize=6)
    ax2.set_ylim(88, 101)
    ax2.set_xlabel("Congestion-hour share")
    ax2.set_ylabel("Reward success (%)")
    ax2.legend(loc="center right", handlelength=1.2)

    # (c) tokenized revenue vs adoption ceiling
    x, rev = sweep("ADOPTION_CEILING", "revenue_tokenized_usd", 1e-3)
    ax3.plot(x, rev, color=AQUA, lw=1.5, marker="o", ms=2.8)
    ax3.set_ylim(0, max(rev) * 1.2)
    ax3.set_xlabel("Adoption ceiling")
    ax3.set_ylabel("Tokenized rev. (k\\$)")

    # (d) private ledger size vs adoption ceiling
    x, gb = sweep("ADOPTION_CEILING", "storage_gb_week26")
    ax4.plot(x, gb, color=VIOLET, lw=1.5, marker="o", ms=2.8)
    ax4.set_ylim(0, max(gb) * 1.25)
    ax4.set_xlabel("Adoption ceiling")
    ax4.set_ylabel("Ledger size (GB)")

    save(fig, "fig7_sensitivity.pdf")


def main():
    fig_latency()
    fig_nft_mint()
    fig_scalability()
    fig_notarization_storage()
    fig_sensitivity()
    with open(C.RESULTS_DIR / "kpi_summary.json") as f:
        print(json.dumps(json.load(f), indent=2))


if __name__ == "__main__":
    main()
