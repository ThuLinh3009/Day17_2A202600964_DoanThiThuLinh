"""Thực Hành 1 — Agent trace -> Bronze: the code of the data flywheel.

Day 13's telemetry SDK emits one trace per agent turn as a *nested span tree*
(root `invoke_agent` -> child `retrieve_policy`, `chat`, ...), with attributes
following the OpenTelemetry GenAI semantic conventions (`gen_ai.*`). This module
is the *consumer*: it flattens those trees into one flat Bronze row per span so
the agent's own behaviour becomes queryable, append-only data — the raw material
every downstream dataset (eval, fine-tune, DPO) is built from.

Bronze rule #1 still holds: we land the spans verbatim (raw JSON kept in a column)
and never edit them. Silver/Gold/derived datasets are rebuildable from here.
"""
from __future__ import annotations
import json
from pathlib import Path

import duckdb

from . import config

BRONZE_SPANS = "bronze_agent_spans"


def load_traces(path: Path | None = None) -> list[dict]:
    """Read the trace export (a JSON array of root spans)."""
    path = path or config.TRACES_JSON
    return json.loads(Path(path).read_text(encoding="utf-8"))


def flatten(root: dict, trace_id: str | None = None, depth: int = 0) -> list[dict]:
    """Recursively flatten one span tree into a list of flat span rows.

    The recursion is the whole trick: a tree of arbitrary depth becomes a tidy
    table you can `GROUP BY trace_id`. We hoist the load-bearing `gen_ai.*` and
    app attributes into real columns and keep the rest as JSON for completeness.
    """
    trace_id = trace_id or root.get("trace_id") or root["span_id"]
    attrs = root.get("attributes", {})
    row = {
        "trace_id": trace_id,
        "span_id": root["span_id"],
        "parent_id": root.get("parent_id"),
        "name": root["name"],
        "depth": depth,
        "duration_ms": root.get("duration_ms", 0),
        "status": root.get("status", "ok"),
        "model": attrs.get("gen_ai.request.model"),
        "input_tokens": attrs.get("gen_ai.usage.input_tokens"),
        "output_tokens": attrs.get("gen_ai.usage.output_tokens"),
        "tool_name": attrs.get("tool.name"),
        "user_input": attrs.get("input"),
        "agent_output": attrs.get("output"),
        "error_type": attrs.get("error.type"),
        "split": attrs.get("split"),
        "attributes_json": json.dumps(attrs, ensure_ascii=False),
    }
    rows = [row]
    for child in root.get("children", []):
        rows.extend(flatten(child, trace_id=trace_id, depth=depth + 1))
    return rows


def traces_to_bronze(con: duckdb.DuckDBPyConnection, traces: list[dict]) -> int:
    """Land every span of every trace into the Bronze span table. Returns row count."""
    import pandas as pd

    rows = [r for root in traces for r in flatten(root)]
    df = pd.DataFrame(rows)
    con.register("spans_df", df)
    con.execute(f"DROP TABLE IF EXISTS {BRONZE_SPANS}")
    con.execute(f"CREATE TABLE {BRONZE_SPANS} AS SELECT * FROM spans_df")
    (n,) = con.execute(f"SELECT count(*) FROM {BRONZE_SPANS}").fetchone()
    return n


def trace_summary(con: duckdb.DuckDBPyConnection) -> "pd.DataFrame":
    """Gold-ish rollup: per-trace cost + latency + outcome (what an analyst reads)."""
    return con.execute(
        f"""
        SELECT trace_id,
               max(user_input)                              AS user_input,
               max(agent_output)                            AS agent_output,
               max(CASE WHEN depth=0 THEN status END)       AS outcome,
               sum(coalesce(input_tokens,0)+coalesce(output_tokens,0)) AS total_tokens,
               max(CASE WHEN depth=0 THEN duration_ms END)  AS latency_ms,
               count(*)                                     AS n_spans
        FROM {BRONZE_SPANS}
        GROUP BY trace_id
        ORDER BY trace_id
        """
    ).fetchdf()
