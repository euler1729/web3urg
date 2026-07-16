"""Central configuration for the URG Web3 VEDM simulation study.

All parameters used by generate_data.py, run_experiments.py and
make_figures.py live here so that a single edit re-parameterizes the
whole pipeline. The random seed makes every run fully reproducible.
"""

from pathlib import Path

# ---------------------------------------------------------------- paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
FIGURES_DIR = BASE_DIR / "figures"
MANUSCRIPT_PDF_DIR = BASE_DIR.parent / "manuscript" / "pdf"

SEED = 514

# ------------------------------------------------- ecosystem (synthetic)
N_HOUSEHOLDS = 500          # registered households at full adoption
SIM_WEEKS = 26              # observation horizon (one growing season)
ADOPTION_MIDPOINT_WEEK = 9  # logistic adoption curve midpoint
ADOPTION_RATE = 0.55        # logistic steepness
ADOPTION_CEILING = 0.93     # fraction of households active by week 26

PLOTS_PER_HOUSEHOLD_MEAN = 1.25   # 1-3 rooftop plots per household
SENSOR_READINGS_PER_DAY = 48      # one reading every 30 min per plot
SENSOR_READING_BYTES = 120        # raw reading stored on private ledger
DAILY_MERKLE_RECORD_BYTES = 512   # per-plot daily aggregate record

HARVEST_INTERVAL_WEEKS_MEAN = 3.0   # a plot yields a batch every ~3 weeks
HARVEST_SEASON_START_WEEK = 4       # no harvests before crops mature
P_BATCH_SOLD = 0.72                 # sold vs. self-consumed / shared
P_SALE_TOKENIZED = 0.84             # sold through NFT marketplace vs. cash
BATCH_PRICE_USD = (3.0, 12.0)       # uniform price range per batch
P_RECORD_ONCHAIN = 0.965            # produce records successfully anchored

TOKENS_PER_ACTION = 10          # reward tokens per verified sustainable action
ACTIONS_PER_WEEK_MEAN = 2.2     # composting / water-saving actions per household
P_REDEEM_WITHIN_HORIZON = 0.55  # probability a token batch is redeemed
                                # (midpoint of retail loyalty redemption benchmarks)
NFT_RETENTION_DAYS = 30         # holding horizon used for the retention KPI
P_NFT_RETAINED = 0.81           # batch NFT still held after 30 days
WORKSHOP_EVERY_WEEKS = 2        # metaverse workshop cadence
WORKSHOP_ATTENDANCE_FRAC = 0.34 # share of active households attending

# ------------------------------------------------ layer-2 chain model
BLOCK_TIME_S = 2.1              # Polygon-PoS-like block interval
BLOCK_TIME_JITTER_S = 0.25
RPC_OVERHEAD_MEAN_S = 0.25      # wallet/RPC round-trip before inclusion race
P_INCLUDE_NORMAL = 0.75         # per-block inclusion probability, normal load
P_INCLUDE_SPIKE = 0.35          # per-block inclusion probability, congestion
P_SPIKE_HOUR = 0.05             # fraction of hours in congestion regime
GAS_PRICE_MEDIAN_GWEI = 35.0    # lognormal median
GAS_PRICE_SIGMA = 0.35
SPIKE_GAS_MULTIPLIER = (3.0, 8.0)
POL_USD = 0.42                  # native token price used for USD conversion

GAS_USED = {                    # gas per contract call
    "registerPlot": 145_000,
    "mintHarvestNFT": 212_000,
    "marketplacePurchase": 96_000,
    "rewardTransfer": 24_000,   # per transfer inside a batched multisend
    "notarizeRoot": 88_000,
}
ONCHAIN_SAMPLES = 4000          # Monte-Carlo samples per transaction type

# --------------------------------------- platform (off-chain) service model
PLATFORM_OPS = {                # mean service demand in ms (gamma, k=4)
    "registerPlot": 62.0,
    "recordSensorBatch": 44.0,
    "redeemToken": 55.0,
    "marketplaceOrder": 78.0,
}
PLATFORM_SAMPLES = 5000

# ------------------------------------------------- closed-loop load test
LOAD_SERVERS = 16               # application worker pool size
LOAD_SERVICE_MEAN_MS = 40.0     # lognormal service time mean
LOAD_SERVICE_SIGMA = 0.45
LOAD_THINK_TIME_S = 3.5         # exponential user think time
LOAD_TIMEOUT_MS = 2000.0        # requests beyond this count as failures
LOAD_BASE_FAILURE = 0.001       # residual failure rate independent of load
LOAD_USER_LEVELS = [100, 200, 400, 600, 800, 1000, 1200, 1400, 1600, 1800,
                    2000, 2200, 2400]
LOAD_SIM_SECONDS = 240.0        # simulated wall-clock per load level
LOAD_WARMUP_SECONDS = 40.0
SLA_P95_MS = 500.0              # scalability acceptance thresholds
SLA_SUCCESS = 0.995

# --------------------------------------------- reward distribution model
REWARD_CHUNK_SIZE = 100         # transfers per multisend transaction
P_CHUNK_FAIL_NORMAL = 0.02      # underpriced gas / nonce race, normal hours
P_CHUNK_FAIL_SPIKE = 0.25       # same, during congestion
MAX_RETRIES = 2                 # resubmissions with bumped gas
P_TRANSFER_FAIL = 0.004         # individual transfer reverts (wallet state)
P_TRANSFER_RETRY_OK = 0.60      # reverted transfer succeeds on manual retry

# ------------------------------------------------- notarization batching
NOTARIZE_INTERVALS_H = [0.25, 1.0, 6.0, 24.0]

# --------------------------------------------- sensitivity analysis sweeps
# One-at-a-time sweeps around the baseline; each key is a config attribute
# overridden by run_sensitivity.py while everything else stays at baseline.
SENSITIVITY = {
    "GAS_PRICE_MEDIAN_GWEI": [17.5, 35.0, 70.0, 105.0],   # 0.5x - 3x baseline
    "P_SPIKE_HOUR": [0.02, 0.05, 0.10, 0.15],
    "P_REDEEM_WITHIN_HORIZON": [0.30, 0.45, 0.55, 0.70],
    "ADOPTION_CEILING": [0.50, 0.70, 0.93],
}

# ------------------------------------------------------- KPI targets
TARGETS = {
    "platform_p95_ms": 250.0,
    "mint_p95_s": 10.0,
    "mint_cost_usd": 0.05,
    "reward_success": 0.995,
    "concurrent_users": 1000,
    "notarize_daily_usd": 1.0,
    "storage_gb_26w": 5.0,
}
