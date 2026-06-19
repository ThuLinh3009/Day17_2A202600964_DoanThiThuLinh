# Bonus Design — Real-World Data Pipeline: Vietnamese E-Commerce Agent Flywheel

## Problem Statement

A Vietnamese e-commerce platform (think Tiki/Shopee scale: ~5 M orders/day, ~200 K
concurrent users peak) deploys a customer-service LLM agent that handles returns,
warranty claims, and product queries. The agent runs on Claude Sonnet. Every agent
turn produces an OpenTelemetry `gen_ai.*` trace. The goal is to build the **data
pipeline** that transforms those traces into:

1. A continuously refreshed **eval golden set** (so QA always uses held-out data).
2. **DPO preference pairs** for weekly fine-tune cycles.
3. **Point-in-time user features** (lifetime spend, return rate, tier) joined
   correctly to each training row.

**Hard constraints:**
- Vietnamese text: diacritics, mixed Vietnamese/English, teen slang in user inputs.
- Regulatory: Vietnamese Law on Consumer Protection (BVQLNTD) requires a 7-day
  audit trail for all agent decisions affecting returns. Data must not leave Vietnam
  (data residency — VNG Cloud or FPT Cloud only).
- Cost: fine-tune budget is 50 USD/week. All data prep must run on a single r6a.2xlarge
  equivalent (8 vCPU, 64 GB RAM).
- Latency: eval refresh must complete within 2 hours of the nightly batch window
  (02:00–04:00 ICT).

---

## Architecture Sketch

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PRODUCTION                                   │
│  Agent turns ──► Kafka topic (gen_ai.traces, partitioned by user_id) │
│                        │                                             │
└────────────────────────┼────────────────────────────────────────────┘
                         │  (Redpanda on-prem, VNG Cloud)
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      BRONZE LAYER  (append-only)                     │
│  Flink job: flatten span trees ──► bronze_agent_spans (Iceberg)     │
│  Retention: 90 days (audit requirement)  Schema: gen_ai.* columns   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  nightly batch (02:00 ICT)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      SILVER LAYER                                    │
│  dbt model: dedup by (trace_id, span_id)                            │
│  Vietnamese text normaliser: NFC + undiacritics for decontam hash   │
│  Quality gate: pandera schema, quarantine malformed spans           │
└──────┬────────────────────────────────────────────────────────────┬─┘
       │                                                            │
       ▼                                                            ▼
┌─────────────────────────┐                        ┌───────────────────────────┐
│  EVAL GOLDEN SET        │                        │  PREFERENCE PAIRS (DPO)   │
│  split='eval' turns     │                        │  ok-vs-error same prompt  │
│  → eval_golden.jsonl    │                        │  → preference_pairs.jsonl │
│  ASOF join: user tier   │                        │  decontaminate (n-gram    │
│  at trace time          │                        │  + embedding similarity)  │
└─────────────────────────┘                        └───────────────────────────┘
                                                            │
                                                            ▼
                                              ┌─────────────────────────┐
                                              │  Weekly fine-tune        │
                                              │  (DPO on Haiku 4.5,     │
                                              │  50 USD budget)          │
                                              └─────────────────────────┘
```

---

## Open Questions — with Explicit Tradeoffs

### Q1: Streaming ingestion — Kafka/Flink vs batch Airflow?

**Decision: Flink for flattening, Airflow for downstream batch.**

Flink gives sub-second span landing so the 90-day audit trail is always fresh for
regulators. Pure Airflow batch would introduce a 24-hour lag between an agent
decision and its audit record — unacceptable under BVQLNTD. The tradeoff is
operational complexity (Flink cluster vs. simple Airflow DAG). We accept this
because the audit requirement is non-negotiable; everything downstream can still
be batch.

**Rejected alternative:** Lambda-architecture dual write (stream + batch recompute).
Too expensive on Vietnamese cloud pricing (doubles egress) and the "batch layer
always wins" reconciliation logic is a maintenance burden with no benefit here —
the stream is the truth.

### Q2: Decontamination — exact match vs n-gram vs embedding similarity?

**Decision: 13-gram Jaccard for Vietnamese + embedding cosine fallback.**

Vietnamese question paraphrases share 4–6 character n-grams even after whitespace
normalisation ("trả hàng widget" ↔ "tôi muốn trả widget"). Pure exact match (as
in `dataset.py`) misses these. Embedding cosine (threshold 0.85) catches semantic
duplicates but is slow (500 ms/pair at scale). The staged approach: 13-gram Jaccard
(fast, zero-key) first, then embedding only for borderline cases (0.7 < Jaccard < 1.0).

**Tradeoff:** n-gram over-rejects slightly (conservative); embedding under-rejects
(permissive but slow). Conservative is better here — a contaminated eval is a
silent failure; a slightly smaller training set is recoverable.

### Q3: Point-in-time join — DuckDB ASOF vs Feature Store?

**Decision: DuckDB ASOF JOIN for weekly batch; no feature store yet.**

A dedicated feature store (Feast, Tecton) adds correct point-in-time semantics
at online serving AND training, closing the train/serve skew entirely. But the
weekly batch cadence means skew windows are at most 7 days — acceptable for a
returns-policy agent. The cost of a managed feature store on Vietnamese cloud (~300
USD/month) is not justified until the retraining cadence exceeds daily. At that
threshold, adopt Feast self-hosted on FPT Cloud.

### Q4: Eval set curation — automated vs human-curated holdout?

**Decision: automated `split='eval'` tagging at trace time + quarterly human audit.**

Fully manual curation is too slow for a 5 M order/day platform. Automated tagging
(mark every 50th successful trace as `split='eval'`) gives a statistically
representative holdout without human bottleneck. The risk is that the automated
sample drifts from real user distribution (seasonal product mix shifts). Quarterly
human spot-checks on 200 sampled eval rows catch distribution drift before it
poisons the eval signal.

### Q5: Data residency — how to enforce "no data leaves Vietnam"?

**Decision: deploy Kafka + Flink + DuckDB warehouse on VNG Cloud Region (HCM1)
with network policy blocking egress to foreign IP ranges.**

The naive approach (just configure cloud provider settings) is insufficient — a
misconfigured SDK can silently send telemetry to a US endpoint. Defense-in-depth:
(a) VNG Cloud VPC with no internet gateway on data subnets; (b) OTel collector
configured to reject exports to non-RFC-1918 IPs; (c) weekly audit of DNS logs for
foreign lookups from data pipeline hosts.

### Q6: Cost control — how to keep fine-tune within 50 USD/week?

**Decision: deduplicate preference pairs by (prompt n-gram cluster), cap at 2 000
pairs/week, fine-tune Haiku 4.5 (not Sonnet).**

Fine-tuning cost scales linearly with token count. At 2 000 pairs × ~400 tokens avg
= 800 K tokens × Claude fine-tune pricing ≈ 40–45 USD — within budget. The
tradeoff is that fewer pairs means slower capability improvement. Monitoring KPI:
if weekly eval score improvement drops below 0.5 percentage points for two
consecutive weeks, investigate whether the pair cap is the bottleneck (vs. data
quality or learning rate).

---

## Rejected Alternative: End-to-End LLM-as-Judge Eval

An LLM-as-judge approach (use GPT-4o/Opus to score every agent response) removes
the dependency on human-curated `split='eval'` turns and would scale automatically.
**Rejected because:**
1. Cost: ~0.01 USD/judgment × 5 M turns/day = 50 K USD/day — 1 000× over budget.
2. Data residency: sending Vietnamese PII-containing user queries to an OpenAI US
   endpoint violates the constraint.
3. Judge bias: LLM judges are known to favour their own output style, creating a
   circularity when the same provider trains both agent and judge.

---

## Vietnamese-Data Awareness

Vietnamese customer messages mix formal Vietnamese, English product names, and
teen slang (e.g., "đổi hàng đc không ad ơi" = "can I exchange this, admin?").
Two pipeline implications:

1. **Decontamination hashing** must use Unicode NFC normalisation before n-gram
   computation — otherwise "trả hàng" and "tra hang" (typed without diacritics on
   mobile) are not deduplicated.
2. **Gold aggregations** must treat Vietnamese holiday spikes (Tết, 9/9 sale) as
   known anomalies, not data-quality errors. The quarantine gate should have a
   `--bypass-anomaly` flag for known sale windows to avoid false DLQ fills.

---

## Summary

The core insight is that the same Medallion + flywheel architecture from the lab
scales to production with three additions: (a) streaming ingestion for audit
compliance, (b) Vietnamese-aware decontamination, and (c) ASOF point-in-time joins
deferred to a feature store only when retraining cadence demands it. The bottleneck
at Vietnamese scale is not compute — it is **eval quality**: a contaminated eval
set silently inflates metrics while the agent degrades in production. Every design
decision above is optimised to keep that signal clean.

Word count: ~820
