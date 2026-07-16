"""Generate the synthetic URG ecosystem dataset.

Produces weekly-resolution activity data for a 26-week growing season:
household adoption, rooftop plots, sensor volume, harvest batches and
their NFTs, marketplace sales, token reward issuance/redemption and
metaverse workshop attendance. Output CSVs land in simulation/data/.
"""

import csv
import numpy as np

import config as C


def logistic_adoption(week: np.ndarray) -> np.ndarray:
    """Fraction of households onboarded by a given week."""
    return C.ADOPTION_CEILING / (
        1.0 + np.exp(-C.ADOPTION_RATE * (week - C.ADOPTION_MIDPOINT_WEEK))
    )


def main() -> None:
    rng = np.random.default_rng(C.SEED)
    C.DATA_DIR.mkdir(exist_ok=True)

    weeks = np.arange(1, C.SIM_WEEKS + 1)
    active_households = np.round(C.N_HOUSEHOLDS * logistic_adoption(weeks)).astype(int)

    # --- households and plots -------------------------------------------
    onboard_week = np.searchsorted(active_households, np.arange(1, active_households[-1] + 1))
    n_households = active_households[-1]
    plots_per_household = 1 + rng.binomial(2, (C.PLOTS_PER_HOUSEHOLD_MEAN - 1) / 2.0,
                                           size=n_households)

    with open(C.DATA_DIR / "households.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["household_id", "onboard_week", "n_plots"])
        for i in range(n_households):
            w.writerow([i + 1, int(onboard_week[i]) + 1, int(plots_per_household[i])])

    # --- weekly panel -----------------------------------------------------
    rows = []
    nft_rows = []
    nft_id = 0
    for wk, n_active in zip(weeks, active_households):
        mask = (onboard_week + 1) <= wk
        n_plots = int(plots_per_household[mask].sum())

        # sensor volume on the private ledger
        readings = n_plots * C.SENSOR_READINGS_PER_DAY * 7

        # harvest batches -> NFT mints
        if wk >= C.HARVEST_SEASON_START_WEEK:
            lam = n_plots / C.HARVEST_INTERVAL_WEEKS_MEAN
            batches = rng.poisson(lam)
        else:
            batches = 0

        sold = rng.binomial(batches, C.P_BATCH_SOLD)
        tokenized = rng.binomial(sold, C.P_SALE_TOKENIZED)
        cash_sales = sold - tokenized
        prices_tok = rng.uniform(*C.BATCH_PRICE_USD, size=tokenized)
        prices_cash = rng.uniform(*C.BATCH_PRICE_USD, size=cash_sales)
        onchain_records = rng.binomial(batches, C.P_RECORD_ONCHAIN)

        for _ in range(batches):
            nft_id += 1
            nft_rows.append([
                nft_id, wk,
                int(rng.random() < C.P_NFT_RETAINED),   # still held after 30 d
            ])

        # token economy
        actions = rng.poisson(C.ACTIONS_PER_WEEK_MEAN * n_active)
        tokens_issued = actions * C.TOKENS_PER_ACTION
        tokens_redeemed = rng.binomial(tokens_issued, C.P_REDEEM_WITHIN_HORIZON)

        # metaverse workshops
        if wk % C.WORKSHOP_EVERY_WEEKS == 0:
            attendance = rng.binomial(n_active, C.WORKSHOP_ATTENDANCE_FRAC)
        else:
            attendance = 0

        rows.append([
            wk, n_active, n_plots, readings, batches, sold, tokenized,
            round(float(prices_tok.sum()), 2), round(float(prices_cash.sum()), 2),
            onchain_records, tokens_issued, tokens_redeemed, attendance,
        ])

    with open(C.DATA_DIR / "weekly_activity.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "week", "active_households", "active_plots", "sensor_readings",
            "harvest_batches", "batches_sold", "batches_tokenized",
            "revenue_tokenized_usd", "revenue_cash_usd", "records_onchain",
            "tokens_issued", "tokens_redeemed", "workshop_attendance",
        ])
        w.writerows(rows)

    with open(C.DATA_DIR / "nfts.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["nft_id", "mint_week", "retained_30d"])
        w.writerows(nft_rows)

    total_batches = sum(r[4] for r in rows)
    print(f"households={n_households}  plots={int(plots_per_household.sum())}  "
          f"weeks={C.SIM_WEEKS}  harvest_batches={total_batches}  nfts={nft_id}")


if __name__ == "__main__":
    main()
