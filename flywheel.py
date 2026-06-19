"""The agent-data FLYWHEEL pipeline (Thực Hành 1/3/4 from the deck).

    python flywheel.py

Turns agent telemetry into training/eval data, zero-key, DuckDB-only:
  traces (gen_ai.* span trees) -> Bronze spans -> {eval set, DPO pairs}
  + a point-in-time feature join showing train/serve parity.

This is the loop that makes an agent improve from its own production traffic:
Day 13 emits the traces -> Day 17 turns them into datasets -> Day 22 trains on them.
"""
import duckdb

from pipeline import config
from pipeline.traces import load_traces, traces_to_bronze, trace_summary
from pipeline.dataset import (
    build_eval_set, build_preference_pairs, decontaminate, write_jsonl,
)
from pipeline.features import point_in_time_features, naive_leaky_features


def main() -> dict:
    con = duckdb.connect(":memory:")
    try:
        # 1) Ingest agent traces into Bronze (recursive span flatten).
        traces = load_traces()
        n_spans = traces_to_bronze(con, traces)
        summary = trace_summary(con)

        # 2) Curate datasets from the traces.
        eval_set = build_eval_set(con)
        pairs = build_preference_pairs(con)
        clean_pairs = decontaminate(pairs, eval_set)
        n_eval = write_jsonl(eval_set, config.EVAL_JSONL)
        n_pref = write_jsonl(clean_pairs, config.PREF_JSONL)

        # 3) Point-in-time features (train/serve parity).
        pit = point_in_time_features(con)
        leaky = naive_leaky_features(con)

        print("=== Day 17 flywheel: agent traces -> datasets ===")
        print(f"  spans landed in Bronze   : {n_spans} (from {len(traces)} traces)")
        print(f"  eval golden rows         : {n_eval}  -> {config.EVAL_JSONL.name}")
        print(f"  preference pairs (raw)   : {len(pairs)}")
        print(f"  preference pairs (clean) : {n_pref}  -> {config.PREF_JSONL.name}  "
              f"({len(pairs) - n_pref} dropped by decontamination)")
        print("\nPer-trace summary (the analyst view):")
        print(summary.to_string(index=False))
        print("\nPoint-in-time features (ASOF, correct) vs naive (leaky):")
        merged = pit.merge(leaky, on=["user_id", "event_ts"])
        print(merged.to_string(index=False))
        leaks = int((merged["spend_leaky"] > merged["spend_at_event"]).sum())
        print(f"\n  rows where the naive join LEAKED a future value: {leaks}")
        return {
            "n_spans": n_spans, "n_eval": n_eval, "n_pref": n_pref,
            "n_pairs_raw": len(pairs), "leaks": leaks,
        }
    finally:
        con.close()


if __name__ == "__main__":
    main()
