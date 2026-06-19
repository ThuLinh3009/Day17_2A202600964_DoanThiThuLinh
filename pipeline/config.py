"""Central config. Everything runs locally on DuckDB — no API keys, no cloud."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_CSV = DATA_DIR / "raw_orders.csv"
DOCS_DIR = DATA_DIR / "docs"
TRACES_JSON = DATA_DIR / "traces" / "agent_traces.json"   # agent flywheel input
WAREHOUSE = ROOT / "warehouse.duckdb"      # the local "lakehouse"
QUARANTINE = ROOT / "quarantine.csv"       # dead-letter / quarantine sink

# Derived AI datasets (Thực Hành 4) land here, ready for Day 22 SFT/DPO.
DATASETS_DIR = ROOT / "datasets"
EVAL_JSONL = DATASETS_DIR / "eval_golden.jsonl"
PREF_JSONL = DATASETS_DIR / "preference_pairs.jsonl"

# Bronze keeps raw forever (append-only). Silver dedups. Gold aggregates.
BRONZE = "bronze_orders"
SILVER = "silver_orders"
GOLD = "gold_daily_orders"
