# Lab 17 — Data Pipeline Engineering (Track 2)

> 🇻🇳 Bản tiếng Việt (mặc định): [`README.md`](README.md)

Build a real, runnable data pipeline for **AI** data — not just a Medallion ETL,
but the **agent-data flywheel** that turns an agent's own traffic into the eval
and fine-tuning datasets that make it better.

```
raw orders  ─▶ ingest ─▶ validate(gate) ─▶ dedup→Gold ─▶ load        (Medallion core)
agent traces ─▶ Bronze spans ─▶ eval set + DPO pairs ─▶ point-in-time features  (flywheel)
docs ─▶ chunk→embed (vector)   |   docs ─▶ triples→graph (knowledge graph)       (RAG/KG)
```

Everything runs **zero-key, cross-platform** on DuckDB + pure Python. The **lite
path** needs only `pip install`. Docker and dbt are optional.

This lab pays off the lecture directly:
- the seed orders have **~30% duplicates + 3 malformed rows** → dedup at Silver,
  quarantine the bad ones so they never reach a model (§2/§9);
- the seed **agent traces** carry successes *and* failures → curate an eval set
  and **DPO preference pairs**, with **decontamination** so you never train on
  what you grade on (§12 Thực Hành 1/3/4);
- the naive feature join **leaks the future** → fix it with an `ASOF` point-in-time
  join (§11 training-serving skew).

---

## Quick start (lite path — graded core)

```bash
make setup          # python -m venv .venv + install (or do it by hand, below)
make verify         # end-to-end smoke test — expect "ALL PASS" (16 checks)
make run            # Medallion pipeline: dedup + quarantine + Gold
make flywheel       # agent traces -> Bronze -> eval/DPO datasets + PIT features
make kg             # bonus: knowledge graph from docs
make test           # pytest (18 tests)
```

Without `make`:

```bash
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python verify.py && python main.py && python flywheel.py && python kg_demo.py
pytest -q
```

> **Python version:** the lite path runs on **Python 3.10+** (tested on 3.14).
> The **dbt track needs Python 3.10–3.13** — dbt does not support 3.14 yet.

---

## What's in the box

| Track | File(s) | What you learn |
|---|---|---|
| **T1 Medallion ETL/ELT** | `pipeline/extract.py`, `transform.py` | Bronze (raw, append-only) → Silver (typed, **deduped**) → Gold (features) on DuckDB |
| **T2 Orchestration** | `pipeline/dag.py`, `main.py` | A tiny pure-Python DAG runner (topological order, deps) — Airflow's shape without the weight |
| **T3 Quality gates** | `pipeline/validate.py` | Pandera schema-as-contract; **quarantine / DLQ** for bad records; `lazy=True` collects all failures |
| **T4 dbt** | `dbt_project/` | dbt-duckdb staging→gold models, `not_null`/`unique` tests **+ a unit test** for dedup logic |
| **T5 Streaming** | `pipeline/streaming.py` | Partition-by-key topic + **idempotent consumer** (dedup on event id) — Kafka's core idea, no broker |
| **T6 Agent flywheel** | `pipeline/traces.py`, `flywheel.py` | Recursively **flatten `gen_ai.*` span trees into Bronze** — the agent's own behaviour becomes data |
| **T7 Dataset curation** | `pipeline/dataset.py` | Eval golden set + **DPO `(prompt, chosen, rejected)` pairs** from ok-vs-error turns, with **decontamination** |
| **T8 Point-in-time features** | `pipeline/features.py` | DuckDB **`ASOF JOIN`** for train/serve parity; the naive join is shown to **leak the future** |
| **Bonus RAG** | `pipeline/embed.py` | unstructured → recursive chunk → embedding → store (zero-key hash embedder) |
| **Bonus KG** | `pipeline/kg.py`, `kg_demo.py` | docs → (entity, relation, entity) **triples → graph → real 2-hop traversal**, vs a vector foil that can't bridge split facts (§13) |
| **Bonus Docker** | `docker/` | The same pipeline on **real Airflow 3 + Redpanda** |

---

## The agent-data flywheel (T6–T8) — the heart of this lab

Day 13 instrumented the cumulative agent and emitted one **trace per turn**: a
nested tree of spans (`invoke_agent` → `retrieve_policy` → `chat`) with
OpenTelemetry `gen_ai.*` attributes. `data/traces/agent_traces.json` is a sample
of exactly that export (some turns succeed, some fail with `ToolError`,
`Refusal`, `Hallucination`).

1. **`traces.py` — trace → Bronze.** `flatten()` recurses the span tree into one
   flat row per span (the trick that makes a tree queryable). `traces_to_bronze`
   lands them append-only; `trace_summary` rolls each trace up to cost + latency
   + outcome.
2. **`dataset.py` — Bronze → datasets.** `build_eval_set` takes the **curated
   holdout** (`split='eval'`) successful turns as your benchmark.
   `build_preference_pairs` mines `(prompt, chosen, rejected)` triples by pairing
   a good answer with a failed answer to the same question.
   `decontaminate` then **drops every pair whose prompt is in the eval set** —
   on the seed data, raw 3 pairs → **1 clean pair (2 dropped)**. Skipping this is
   the #1 way an eval silently lies.
3. **`features.py` — point-in-time correctness.** `point_in_time_features` uses
   `ASOF JOIN` so each event sees only the feature value known *at or before* it;
   `naive_leaky_features` shows the "latest value" join leaking a future
   `lifetime_spend` into the training row.

The output datasets land in `datasets/` ready for **Day 22** (SFT/DPO). That's
the loop: Day 13 produces traces → **Day 17 turns them into data** → Day 22 trains.

---

## How the gate + dedup work (T1–T3)

`data/raw_orders.csv` has real orders, **5 exact duplicate rows** (order_ids 1–5
each appear twice), and **3 bad records** — a null `user_id`, a negative
`amount`, and an out-of-vocabulary `status`.

1. **Extract** → Bronze, unchanged. Never edited; rebuildable source of truth.
2. **Validate** → Pandera splits clean vs bad; bad rows → `quarantine.csv` (DLQ).
   One bad row never halts the run.
3. **Transform** → Silver dedups on `order_id`; Gold aggregates **completed**
   orders by day.

`verify.py` asserts all of it (16 checks): dupes dropped, exactly 3 quarantined,
no duplicate `order_id` survives, idempotent streaming, embedding ingestion,
**trace→Bronze flatten, eval/DPO curation, decontamination, ASOF anti-leak, and
the knowledge graph**.

---

### dbt track (optional, Python ≤ 3.13)

```bash
python3.13 -m venv .venv-dbt && . .venv-dbt/bin/activate
pip install -r requirements-dbt.txt
cd dbt_project && DBT_PROFILES_DIR=. dbt build      # seed → run → test (expect PASS=11)
```

### Docker bonus (optional)

```bash
docker compose -f docker/docker-compose.yml up      # Airflow UI at http://localhost:8080
```

---

## Extension exercises (ungraded, for depth)

0. **Fuzzy decontamination**: `dataset.decontaminate` is exact-match only — a
   paraphrased eval prompt still leaks. Add n-gram (13-gram) or embedding-similarity
   matching (reuse `embed.py`) and prove a reworded duplicate gets dropped (§12).
1. **Real embeddings**: swap `embed.py`'s hash embedder for a local
   sentence-transformers model; add incremental re-embedding keyed on a content
   hash so only changed chunks are re-embedded (deck §3). See `BONUS-CHALLENGE.md`.
2. **LLM KG extraction**: replace the deterministic extractor in `kg.py` with an
   LLM + entity resolution (deck §13). See `BONUS-CHALLENGE.md`.
3. **Data contract**: write an ODCS `datacontract.yaml` for the orders table and
   wire `datacontract test` into a CI step (deck §10).
4. **Backfill safety**: make `main.py` idempotent under repeated runs with a
   `--date` backfill window (deck §14). Prove re-running doesn't double rows.

Observability, lineage, and anomaly detection for this pipeline are **Day 27**;
the lakehouse table formats it lands in are **Day 18**; the vector/feature stores
it feeds are **Day 19**.

---

## Grading & submission

See [`rubric.md`](rubric.md) (100 core + 20 bonus) and
[`submission/REFLECTION.md`](submission/REFLECTION.md). Submit a **public GitHub
URL** into the LMS Day-17 box — no PR. New to AI-assisted workflows? Read
[`VIBE-CODING.md`](VIBE-CODING.md) first.
