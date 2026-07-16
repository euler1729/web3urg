"""One-at-a-time sensitivity analysis over the assumed parameters.

For each parameter/value pair in config.SENSITIVITY, the affected parts
of the pipeline are re-run with that single override (everything else at
baseline, same seed) and the KPIs that parameter influences are
recorded. Output: results/sensitivity.csv with one row per sweep point.

Swept parameters and the KPIs they drive:
  GAS_PRICE_MEDIAN_GWEI    -> NFT mint cost (mean/p95), notarization cost/day
  P_SPIKE_HOUR             -> reward delivery success (first / final)
  P_REDEEM_WITHIN_HORIZON  -> token redemption rate
  ADOPTION_CEILING         -> storage growth, revenue, workshop attendance
"""

import csv
import numpy as np

import config as C
import generate_data
import run_experiments as X


def with_override(name, value):
    """Set config attribute, returning the original for restoration."""
    original = getattr(C, name)
    setattr(C, name, value)
    return original


def onchain_kpis(rng):
    rows = X.experiment_onchain(rng)
    mint = np.array([r[2] for r in rows if r[0] == "mintHarvestNFT"])
    price, _ = X.sample_gas_price_gwei(rng, 10_000)
    notarize_day = 24.0 * C.GAS_USED["notarizeRoot"] * float(price.mean()) * 1e-9 * C.POL_USD
    return {
        "mint_cost_mean_usd": round(float(mint.mean()), 5),
        "mint_cost_p95_usd": round(float(np.percentile(mint, 95)), 5),
        "notarize_hourly_daily_cost_usd": round(notarize_day, 4),
    }


def reward_kpis(rng):
    rows = X.experiment_rewards(rng)  # 20 replications, rows: [rep, wk, recipients, ...]
    transfers = sum(r[2] for r in rows)
    return {
        "reward_first_attempt_success": round(1.0 - sum(r[4] for r in rows) / transfers, 4),
        "reward_final_success": round(1.0 - sum(r[5] for r in rows) / transfers, 4),
    }


def ecosystem_kpis():
    weekly = list(csv.DictReader(open(C.DATA_DIR / "weekly_activity.csv")))
    tot = lambda k: sum(float(r[k]) for r in weekly)
    rev_tok, rev_cash = tot("revenue_tokenized_usd"), tot("revenue_cash_usd")
    cum_bytes = sum(
        int(r["sensor_readings"]) * C.SENSOR_READING_BYTES
        + int(r["active_plots"]) * 7 * C.DAILY_MERKLE_RECORD_BYTES
        + int(r["harvest_batches"]) * 2048
        + int(r["tokens_issued"]) * 4
        for r in weekly
    )
    return {
        "token_redemption_rate": round(tot("tokens_redeemed") / tot("tokens_issued"), 3),
        "revenue_tokenized_usd": round(rev_tok, 0),
        "revenue_share_tokenized": round(rev_tok / (rev_tok + rev_cash), 3),
        "active_households_week26": int(weekly[-1]["active_households"]),
        "storage_gb_week26": round(cum_bytes / 1e9, 4),
    }


KPI_FIELDS = [
    "mint_cost_mean_usd", "mint_cost_p95_usd", "notarize_hourly_daily_cost_usd",
    "reward_first_attempt_success", "reward_final_success",
    "token_redemption_rate", "revenue_tokenized_usd", "revenue_share_tokenized",
    "active_households_week26", "storage_gb_week26",
]


def run_point(param, value):
    """Run only the pipeline stages the swept parameter affects."""
    original = with_override(param, value)
    try:
        row = {"parameter": param, "value": value}
        if param in ("P_REDEEM_WITHIN_HORIZON", "ADOPTION_CEILING"):
            generate_data.main()
            row.update(ecosystem_kpis())
        if param in ("GAS_PRICE_MEDIAN_GWEI", "P_SPIKE_HOUR"):
            row.update(onchain_kpis(np.random.default_rng(C.SEED + 1)))
            row.update(reward_kpis(np.random.default_rng(C.SEED + 2)))
        return row
    finally:
        setattr(C, param, original)


def main():
    C.RESULTS_DIR.mkdir(exist_ok=True)
    rows = []
    for param, values in C.SENSITIVITY.items():
        for v in values:
            row = run_point(param, v)
            rows.append(row)
            shown = {k: row[k] for k in KPI_FIELDS if k in row}
            print(f"{param}={v}: {shown}")

    with open(C.RESULTS_DIR / "sensitivity.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["parameter", "value"] + KPI_FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {C.RESULTS_DIR / 'sensitivity.csv'} ({len(rows)} sweep points)")

    # restore baseline dataset for downstream scripts
    generate_data.main()


if __name__ == "__main__":
    main()
