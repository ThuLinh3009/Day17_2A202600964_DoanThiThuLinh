"""Tests for the agent-data flywheel + KG tracks (Thực Hành 1/3/4, §13). Zero-key."""
import duckdb
import pytest

from pipeline.traces import load_traces, flatten, traces_to_bronze, trace_summary, BRONZE_SPANS
from pipeline.dataset import build_eval_set, build_preference_pairs, decontaminate
from pipeline.features import point_in_time_features, naive_leaky_features
from pipeline.kg import extract_triples, build_graph, query, returnable_products
from pipeline import config


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    traces_to_bronze(c, load_traces())
    yield c
    c.close()


def test_flatten_is_recursive():
    root = {"name": "invoke_agent", "trace_id": "x", "span_id": "r", "parent_id": None,
            "status": "ok", "duration_ms": 10,
            "children": [{"name": "chat", "span_id": "c", "parent_id": "r",
                          "status": "ok", "duration_ms": 5, "children": []}]}
    rows = flatten(root)
    assert len(rows) == 2                       # parent + child
    assert {r["depth"] for r in rows} == {0, 1}
    assert all(r["trace_id"] == "x" for r in rows)  # trace_id propagates to children


def test_bronze_has_one_row_per_span(con):
    (n,) = con.execute(f"SELECT count(*) FROM {BRONZE_SPANS}").fetchone()
    assert n == 21                              # total spans across the 8 seed traces


def test_trace_summary_one_row_per_trace(con):
    s = trace_summary(con)
    assert len(s) == 8
    assert set(s["outcome"]) == {"ok", "error"}


def test_eval_set_is_curated_holdout(con):
    ev = build_eval_set(con)
    assert len(ev) == 2                          # only split='eval' successful turns
    assert all(e["reference"] for e in ev)


def test_preference_pairs_have_chosen_and_rejected(con):
    pairs = build_preference_pairs(con)
    assert len(pairs) >= 1
    for p in pairs:
        assert p["chosen"] and p["rejected"] and p["chosen"] != p["rejected"]


def test_decontamination_removes_eval_leakage(con):
    ev = build_eval_set(con)
    pairs = build_preference_pairs(con)
    clean = decontaminate(pairs, ev)
    assert len(clean) < len(pairs)               # at least one overlap dropped
    held = {e["input"].lower() for e in ev}
    assert all(p["prompt"].lower() not in held for p in clean)


def test_point_in_time_join_beats_leaky(con):
    pit = point_in_time_features(con)
    leaky = naive_leaky_features(con)
    m = pit.merge(leaky, on=["user_id", "event_ts"])
    # the naive join inflates at least one row by leaking a future spend value
    assert int((m["spend_leaky"] > m["spend_at_event"]).sum()) >= 1
    # ASOF never returns a value from after the event
    assert (m["spend_at_event"] <= m["spend_leaky"]).all()


def test_kg_extracts_clean_triples():
    triples = extract_triples(
        "Customers may return widgets within 30 days for a full refund. "
        "Gadgets carry a 90-day limited warranty. "
        "Sprockets are final sale and cannot be returned once opened."
    )
    rels = {(s, r) for s, r, _ in triples}
    assert ("widget", "RETURNABLE_WITHIN") in rels
    assert ("gadget", "HAS_WARRANTY") in rels
    assert ("sprocket", "NON_RETURNABLE") in rels


def test_kg_query_and_multi_node():
    graph = build_graph(extract_triples(config.DOCS_DIR.joinpath("sample.md").read_text()))
    assert query(graph, "widget", "RETURNABLE_WITHIN") == [("RETURNABLE_WITHIN", "30 days")]
    rp = returnable_products(graph)
    assert "widget" in rp            # has a return window
    assert "gadget" not in rp        # warranty is NOT returnability
    assert "sprocket" not in rp      # final sale


def test_kg_traverse_is_real_multihop():
    from pipeline.kg import ingest_docs_to_graph, traverse
    g = ingest_docs_to_graph(config.DOCS_DIR)
    hops = traverse(g, "widget", "SHIPS_FROM")
    assert hops, "expected a multi-hop path widget -> accessory -> warehouse"
    assert hops[0]["hops"] == 2                       # genuinely two hops, not one
    assert hops[0]["path"] == ["widget", "accessory", "hanoi fulfillment center"]
    assert "hanoi" in hops[0]["answer"].lower()


def test_vector_foil_fact_is_split_across_chunks():
    from pipeline.kg import vector_foil
    foil = vector_foil(config.DOCS_DIR, "widget", "hanoi")
    # the whole point: subject and answer live in DIFFERENT chunks
    assert foil["chunk_with_subject"] and foil["chunk_with_answer"]
    assert foil["chunk_with_subject"] != foil["chunk_with_answer"]
    assert foil["single_chunk_answers_it"] is False   # flat RAG cannot bridge
