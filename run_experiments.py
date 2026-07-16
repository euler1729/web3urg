"""Run the dual-KPI experiments on the synthetic URG dataset.

Five experiments cover the technical KPI layer of the performance-aware
Web3 VEDM, and the business KPIs are computed from the generated
ecosystem data:

  E1  Platform (off-chain) smart-contract-triggering operation latency
  E2  On-chain transaction confirmation time and USD cost (incl. NFT mint)
  E3  Closed-loop load test: response time / success rate vs. concurrent users
  E4  Weekly token reward distribution reliability (batched multisend + retry)
  E5  Notarization batching cost trade-off and private-ledger storage growth

Outputs: CSV result files in simulation/results/ plus kpi_summary.csv.
"""

import csv
import heapq
import json
import numpy as np

import config as C


# --------------------------------------------------------------------------
# E1: platform operation latency (private ledger + API path), ms scale
# --------------------------------------------------------------------------
def experiment_platform_latency(rng):
    rows = []
    for op, mean_ms in C.PLATFORM_OPS.items():
        # gamma(k=4) service demand + light background contention
        base = rng.gamma(4.0, mean_ms / 4.0, size=C.PLATFORM_SAMPLES)
        contention = rng.exponential(8.0, size=C.PLATFORM_SAMPLES) * (
            rng.random(C.PLATFORM_SAMPLES) < 0.25
        )
        lat = base + contention
        rows += [[op, round(float(v), 2)] for v in lat]
    with open(C.RESULTS_DIR / "platform_latency.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["operation", "latency_ms"])
        w.writerows(rows)
    return rows


# --------------------------------------------------------------------------
# E2: on-chain confirmation time and cost
# --------------------------------------------------------------------------
def sample_gas_price_gwei(rng, n):
    """Lognormal gas price with a congestion-spike regime."""
    price = rng.lognormal(np.log(C.GAS_PRICE_MEDIAN_GWEI), C.GAS_PRICE_SIGMA, n)
    spike = rng.random(n) < C.P_SPIKE_HOUR
    price[spike] *= rng.uniform(*C.SPIKE_GAS_MULTIPLIER, size=spike.sum())
    return price, spike


def experiment_onchain(rng):
    rows = []
    n = C.ONCHAIN_SAMPLES
    for tx in ["registerPlot", "mintHarvestNFT", "marketplacePurchase", "notarizeRoot"]:
        gas = C.GAS_USED[tx]
        price, spike = sample_gas_price_gwei(rng, n)
        p_inc = np.where(spike, C.P_INCLUDE_SPIKE, C.P_INCLUDE_NORMAL)
        blocks = rng.geometric(p_inc)  # blocks waited until inclusion
        block_time = rng.normal(C.BLOCK_TIME_S, C.BLOCK_TIME_JITTER_S, n).clip(1.5)
        t_confirm = (
            rng.gamma(2.0, C.RPC_OVERHEAD_MEAN_S / 2.0, n)   # RPC / wallet overhead
            + rng.uniform(0, block_time)                      # position in current block
            + blocks * block_time
        )
        cost_usd = gas * price * 1e-9 * C.POL_USD
        for t, c_, g, s in zip(t_confirm, cost_usd, price, spike):
            rows.append([tx, round(float(t), 3), round(float(c_), 6),
                         round(float(g), 2), int(s)])
    with open(C.RESULTS_DIR / "onchain_tx.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tx_type", "confirm_time_s", "cost_usd", "gas_price_gwei", "spike"])
        w.writerows(rows)
    return rows


# --------------------------------------------------------------------------
# E3: closed-loop load test (discrete-event simulation, c servers)
# --------------------------------------------------------------------------
def run_load_level(rng, n_users):
    """N users cycling think -> request -> response through c workers."""
    c = C.LOAD_SERVERS
    mu = np.log(C.LOAD_SERVICE_MEAN_MS) - 0.5 * C.LOAD_SERVICE_SIGMA ** 2

    events = []  # (time, seq, kind, user)
    seq = 0
    for u in range(n_users):
        t = rng.exponential(C.LOAD_THINK_TIME_S)
        heapq.heappush(events, (t, seq, "arrive", u)); seq += 1

    busy = 0
    queue = []
    latencies = []
    completed = 0
    t_end = C.LOAD_SIM_SECONDS

    while events:
        t, _, kind, u = heapq.heappop(events)
        if t > t_end:
            break
        if kind == "arrive":
            if busy < c:
                busy += 1
                svc = rng.lognormal(mu, C.LOAD_SERVICE_SIGMA) / 1000.0
                heapq.heappush(events, (t + svc, seq, "done", u)); seq += 1
                # remember arrival time via tuple in done event: encode start
                latencies.append((u, t, t + svc))
            else:
                queue.append((t, u))
        else:  # done
            busy -= 1
            if t > C.LOAD_WARMUP_SECONDS:
                completed += 1
            think = rng.exponential(C.LOAD_THINK_TIME_S)
            heapq.heappush(events, (t + think, seq, "arrive", u)); seq += 1
            if queue:
                t0, uq = queue.pop(0)
                busy += 1
                svc = rng.lognormal(mu, C.LOAD_SERVICE_SIGMA) / 1000.0
                heapq.heappush(events, (t + svc, seq, "done", uq)); seq += 1
                latencies.append((uq, t0, t + svc))

    resp_ms = np.array([(fin - arr) * 1000.0 for _, arr, fin in latencies
                        if arr > C.LOAD_WARMUP_SECONDS])
    timeouts = (resp_ms > C.LOAD_TIMEOUT_MS).mean() if len(resp_ms) else 1.0
    success = (1.0 - timeouts) * (1.0 - C.LOAD_BASE_FAILURE)
    observed = np.minimum(resp_ms, C.LOAD_TIMEOUT_MS)  # timeouts capped, as reported by load tools
    throughput = completed / (t_end - C.LOAD_WARMUP_SECONDS)
    return (float(np.percentile(observed, 50)), float(np.percentile(observed, 95)),
            float(success), float(throughput))


def experiment_load(rng):
    rows = []
    for n in C.LOAD_USER_LEVELS:
        p50, p95, success, x = run_load_level(rng, n)
        rows.append([n, round(p50, 1), round(p95, 1), round(success, 5), round(x, 1)])
        print(f"  load N={n:5d}  p50={p50:7.1f} ms  p95={p95:7.1f} ms  "
              f"success={success:.4f}  X={x:.1f} req/s")
    with open(C.RESULTS_DIR / "load_test.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["concurrent_users", "p50_ms", "p95_ms", "success_rate", "throughput_rps"])
        w.writerows(rows)
    return rows


# --------------------------------------------------------------------------
# E4: weekly reward distribution reliability
# --------------------------------------------------------------------------
REWARD_REPLICATIONS = 20  # replicate seasons to average out chunk-failure noise


def experiment_rewards(rng):
    weekly = list(csv.DictReader(open(C.DATA_DIR / "weekly_activity.csv")))
    rows = []
    for rep in range(REWARD_REPLICATIONS):
        rows += simulate_reward_season(rng, weekly, rep)
    with open(C.RESULTS_DIR / "reward_batches.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rep", "week", "recipients", "chunks", "transfers_failed_first",
                    "transfers_failed_final", "cost_usd"])
        w.writerows(rows)
    return rows


def simulate_reward_season(rng, weekly, rep):
    rows = []
    for r in weekly:
        wk = int(r["week"])
        recipients = int(r["active_households"])
        chunks = int(np.ceil(recipients / C.REWARD_CHUNK_SIZE))
        first_fail_tx = final_fail_tx = 0   # counted at transfer level
        cost = 0.0
        remaining = recipients
        for _ in range(chunks):
            size = min(C.REWARD_CHUNK_SIZE, remaining)
            remaining -= size
            spike = rng.random() < C.P_SPIKE_HOUR
            p_fail = C.P_CHUNK_FAIL_SPIKE if spike else C.P_CHUNK_FAIL_NORMAL
            price = float(sample_gas_price_gwei(rng, 1)[0][0])
            attempts = 1
            failed = rng.random() < p_fail
            if failed:
                first_fail_tx += size
            while failed and attempts <= C.MAX_RETRIES:
                attempts += 1
                price *= 1.25                     # gas bump on resubmission
                failed = rng.random() < p_fail * 0.4
            if failed:
                final_fail_tx += size
                cost += attempts * 21_000 * price * 1e-9 * C.POL_USD
                continue
            # chunk landed: individual transfers may still revert on wallet state
            reverted = rng.binomial(size, C.P_TRANSFER_FAIL)
            recovered = rng.binomial(reverted, C.P_TRANSFER_RETRY_OK)
            first_fail_tx += reverted
            final_fail_tx += reverted - recovered
            gas = size * C.GAS_USED["rewardTransfer"]
            cost += (attempts - 1) * 21_000 * price * 1e-9 * C.POL_USD
            cost += gas * price * 1e-9 * C.POL_USD
        rows.append([rep, wk, recipients, chunks, first_fail_tx, final_fail_tx,
                     round(cost, 4)])
    return rows


# --------------------------------------------------------------------------
# E5: notarization batching + storage growth
# --------------------------------------------------------------------------
def experiment_notarization_storage(rng):
    price, _ = sample_gas_price_gwei(rng, 10_000)
    mean_cost_tx = C.GAS_USED["notarizeRoot"] * float(price.mean()) * 1e-9 * C.POL_USD
    rows = []
    for h in C.NOTARIZE_INTERVALS_H:
        tx_day = 24.0 / h
        rows.append([h, tx_day, round(tx_day * mean_cost_tx, 4), round(h * 30, 1)])
    with open(C.RESULTS_DIR / "notarization.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["interval_h", "tx_per_day", "daily_cost_usd", "mean_anchor_delay_min"])
        w.writerows(rows)

    weekly = list(csv.DictReader(open(C.DATA_DIR / "weekly_activity.csv")))
    storage_rows, cum_bytes = [], 0.0
    for r in weekly:
        plots = int(r["active_plots"])
        readings = int(r["sensor_readings"])
        cum_bytes += (readings * C.SENSOR_READING_BYTES
                      + plots * 7 * C.DAILY_MERKLE_RECORD_BYTES
                      + int(r["harvest_batches"]) * 2048        # batch + NFT metadata
                      + int(r["tokens_issued"]) * 4)            # token ledger entries
        storage_rows.append([int(r["week"]), round(cum_bytes / 1e9, 4)])
    with open(C.RESULTS_DIR / "storage_growth.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["week", "cumulative_gb"])
        w.writerows(storage_rows)
    return rows, storage_rows


# --------------------------------------------------------------------------
# KPI summary (technical + business)
# --------------------------------------------------------------------------
def summarize(platform, onchain, load, rewards, notarization, storage):
    def col(rows, i):
        return np.array([r[i] for r in rows], dtype=float)

    plat = {}
    for op in C.PLATFORM_OPS:
        v = np.array([r[1] for r in platform if r[0] == op])
        plat[op] = (float(np.percentile(v, 50)), float(np.percentile(v, 95)))

    mint = np.array([[r[1], r[2]] for r in onchain if r[0] == "mintHarvestNFT"])
    all_tx = np.array([[r[1], r[2]] for r in onchain])

    sla = [r for r in load if r[2] <= C.SLA_P95_MS and r[3] >= C.SLA_SUCCESS]
    max_users = max(r[0] for r in sla) if sla else 0
    peak_tps = max(r[4] for r in load)

    transfers = col(rewards, 2).sum()
    first_ok = 1.0 - col(rewards, 4).sum() / transfers
    final_ok = 1.0 - col(rewards, 5).sum() / transfers

    weekly = list(csv.DictReader(open(C.DATA_DIR / "weekly_activity.csv")))
    nfts = list(csv.DictReader(open(C.DATA_DIR / "nfts.csv")))
    tot = lambda k: sum(float(r[k]) for r in weekly)
    rev_tok, rev_cash = tot("revenue_tokenized_usd"), tot("revenue_cash_usd")
    last4 = weekly[-4:]

    summary = {
        # ---- technical KPIs
        "platform_latency_p50_ms": {op: round(v[0], 1) for op, v in plat.items()},
        "platform_latency_p95_ms": {op: round(v[1], 1) for op, v in plat.items()},
        "mint_time_mean_s": round(float(mint[:, 0].mean()), 2),
        "mint_time_p95_s": round(float(np.percentile(mint[:, 0], 95)), 2),
        "mint_cost_mean_usd": round(float(mint[:, 1].mean()), 5),
        "mint_cost_p95_usd": round(float(np.percentile(mint[:, 1], 95)), 5),
        "tx_cost_mean_usd": round(float(all_tx[:, 1].mean()), 5),
        "max_concurrent_users_sla": int(max_users),
        "peak_throughput_rps": round(peak_tps, 1),
        "reward_first_attempt_success": round(first_ok, 4),
        "reward_final_success": round(final_ok, 4),
        "notarize_hourly_daily_cost_usd": notarization[1][2],
        "storage_gb_week26": storage[-1][1],
        # ---- business KPIs
        "revenue_share_tokenized": round(rev_tok / (rev_tok + rev_cash), 3),
        "token_redemption_rate": round(tot("tokens_redeemed") / tot("tokens_issued"), 3),
        "nft_retention_30d": round(
            sum(int(r["retained_30d"]) for r in nfts) / len(nfts), 3),
        "records_onchain_share": round(tot("records_onchain") / tot("harvest_batches"), 3),
        "workshop_participation_share_last4w": round(
            max(int(r["workshop_attendance"]) for r in last4)
            / int(last4[-1]["active_households"]), 3),
        "smart_contract_tx_share": round(
            tot("batches_tokenized") / tot("batches_sold"), 3),
    }
    with open(C.RESULTS_DIR / "kpi_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))


def main():
    rng = np.random.default_rng(C.SEED + 1)
    C.RESULTS_DIR.mkdir(exist_ok=True)
    print("E1: platform latency")
    platform = experiment_platform_latency(rng)
    print("E2: on-chain confirmation time and cost")
    onchain = experiment_onchain(rng)
    print("E3: closed-loop load test")
    load = experiment_load(rng)
    print("E4: reward distribution reliability")
    # independent stream so E4 results don't shift when E1-E3 sampling changes
    rewards = experiment_rewards(np.random.default_rng(C.SEED + 4))
    print("E5: notarization batching and storage growth")
    notarization, storage = experiment_notarization_storage(rng)
    summarize(platform, onchain, load, rewards, notarization, storage)


if __name__ == "__main__":
    main()
