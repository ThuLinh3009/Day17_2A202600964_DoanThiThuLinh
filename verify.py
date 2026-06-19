"""End-to-end smoke check (zero-key). Exit 0 = a student's setup works.

    python verify.py
"""
import sys
import duckdb

from pipeline import config
from pipeline.streaming import MiniTopic, consume_features
from pipeline.embed import ingest_docs
from pipeline.traces import load_traces, traces_to_bronze
from pipeline.dataset import build_eval_set, build_preference_pairs, decontaminate
from pipeline.features import point_in_time_features, naive_leaky_features
from pipeline.kg import ingest_docs_to_graph, returnable_products, traverse, vector_foil
import main


_PASSED = 0
_TOTAL = 0


def check(label, cond):
    global _PASSED, _TOTAL
    _TOTAL += 1
    _PASSED += 1 if cond else 0
    mark = "OK " if cond else "XX "
    print(f"  [{mark}] {label}")
    return cond


def run() -> bool:
    ok = True
    stats = main.main()
    ok &= check("extract loaded raw rows", stats["rows_in"] > 0)
    ok &= check("Silver dropped duplicates (the hook)", stats["dropped_dupes"] >= 1)
    ok &= check("gate quarantined bad records", stats["n_quarantined"] == 3)
    ok &= check("Gold produced daily rows", stats["gold_rows"] >= 1)

    con = duckdb.connect(str(config.WAREHOUSE))
    (dupes,) = con.execute(
        f"SELECT count(*) - count(DISTINCT order_id) FROM {config.SILVER}"
    ).fetchone()
    con.close()
    ok &= check("no duplicate order_id remains in Silver", dupes == 0)

    topic = MiniTopic()
    for i, (k, eid, amt) in enumerate(
        [("u1", "e1", 10), ("u1", "e1", 10), ("u2", "e2", 5)]
    ):
        topic.produce(k, {"event_id": eid, "amount": amt})
    feats = consume_features(topic)
    ok &= check("streaming consumer is idempotent", feats["u1"]["orders"] == 1)

    rows = ingest_docs(config.DOCS_DIR)
    ok &= check("doc->chunk->embedding ingestion", len(rows) > 0)

    # --- Agent-data flywheel (Thực Hành 1/3/4) ---
    fcon = duckdb.connect(":memory:")
    traces = load_traces()
    n_spans = traces_to_bronze(fcon, traces)
    ok &= check("agent traces flattened into Bronze spans", n_spans >= len(traces))
    eval_set = build_eval_set(fcon)
    ok &= check("eval golden set curated from traces", len(eval_set) >= 1)
    pairs = build_preference_pairs(fcon)
    clean = decontaminate(pairs, eval_set)
    ok &= check("decontamination drops eval-overlapping pairs", len(clean) < len(pairs))
    ok &= check("at least one clean preference pair survives", len(clean) >= 1)
    pit = point_in_time_features(fcon)
    leaky = naive_leaky_features(fcon)
    m = pit.merge(leaky, on=["user_id", "event_ts"])
    ok &= check("ASOF point-in-time join avoids future leakage",
                int((m["spend_leaky"] > m["spend_at_event"]).sum()) >= 1)
    fcon.close()

    # --- Knowledge Graph bonus (§13) ---
    graph = ingest_docs_to_graph(config.DOCS_DIR)
    ok &= check("knowledge graph built from docs", len(graph) >= 2)
    rp = returnable_products(graph)
    ok &= check("graph query answers 'what is returnable?' = widget only",
                "widget" in rp and "gadget" not in rp)   # warranty != returnable
    hops = traverse(graph, "widget", "SHIPS_FROM")
    ok &= check("graph answers a real 2-hop question (widget->accessory->warehouse)",
                bool(hops) and hops[0]["hops"] == 2 and "hanoi" in hops[0]["answer"].lower())
    foil = vector_foil(config.DOCS_DIR, "widget", "hanoi")
    ok &= check("vector foil: no single chunk answers the multi-hop question",
                foil["single_chunk_answers_it"] is False)
    return ok


if __name__ == "__main__":
    print("=== verify.py: Day 17 lab smoke test ===")
    success = run()
    print(f"\nRESULT: {_PASSED}/{_TOTAL} checks — "
          + ("ALL PASS" if success else "FAILURES ABOVE"))
    sys.exit(0 if success else 1)
