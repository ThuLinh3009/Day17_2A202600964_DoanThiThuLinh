"""Pytest suite — runs zero-key on the seed data. `pytest -q`."""
import duckdb
import pandas as pd
import pytest

from pipeline import config
from pipeline.validate import validate, ORDER_SCHEMA
from pipeline.transform import write_silver, write_gold
from pipeline.extract import extract_to_bronze
from pipeline.streaming import MiniTopic, consume_features
from pipeline.embed import recursive_chunks, embed_text, ingest_docs, EMBED_DIM


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    yield c
    c.close()


def test_extract_loads_all_raw_rows(con):
    n = extract_to_bronze(con)
    assert n == 16  # 16 raw rows incl. duplicates + bad records


def test_gate_quarantines_bad_records():
    df = pd.read_csv(config.RAW_CSV, dtype=str)
    clean, bad = validate(df)
    # bad: null user_id (id 8), negative amount (id 9), bad status (id 10)
    assert len(bad) == 3
    assert len(clean) + len(bad) == len(df)


def test_clean_rows_satisfy_schema():
    df = pd.read_csv(config.RAW_CSV, dtype=str)
    clean, _ = validate(df)
    # validating the clean output again must not raise
    ORDER_SCHEMA.validate(clean, lazy=True)


def test_silver_dedups_on_order_id(con):
    df = pd.read_csv(config.RAW_CSV, dtype=str)
    clean, _ = validate(df)
    stats = write_silver(con, clean)
    assert stats["dropped_dupes"] >= 1
    (dupes,) = con.execute(
        f"SELECT count(*) - count(DISTINCT order_id) FROM {config.SILVER}"
    ).fetchone()
    assert dupes == 0  # no duplicate order_id remains


def test_gold_only_completed(con):
    df = pd.read_csv(config.RAW_CSV, dtype=str)
    clean, _ = validate(df)
    write_silver(con, clean)
    write_gold(con)
    (n_refunded,) = con.execute(
        f"SELECT count(*) FROM {config.SILVER} s "
        f"WHERE s.status='refunded'"
    ).fetchone()
    assert n_refunded >= 1  # refunds exist in silver
    total = con.execute(f"SELECT sum(n_orders) FROM {config.GOLD}").fetchone()[0]
    completed = con.execute(
        f"SELECT count(*) FROM {config.SILVER} WHERE status='completed'"
    ).fetchone()[0]
    assert total == completed  # gold counts only completed


def test_streaming_consumer_is_idempotent():
    topic = MiniTopic()
    topic.produce("u1", {"event_id": "e1", "amount": "10"})
    topic.produce("u1", {"event_id": "e1", "amount": "10"})  # duplicate
    topic.produce("u1", {"event_id": "e2", "amount": "5"})
    feats = consume_features(topic)
    assert feats["u1"]["orders"] == 2  # duplicate e1 ignored
    assert feats["u1"]["spend"] == 15.0


def test_embedding_pipeline_shape():
    chunks = recursive_chunks("word " * 300, size=120, overlap=20)
    assert len(chunks) >= 2
    vec = embed_text("returns policy widget")
    assert len(vec) == EMBED_DIM
    rows = ingest_docs(config.DOCS_DIR)
    assert rows and all(len(r["embedding"]) == EMBED_DIM for r in rows)
