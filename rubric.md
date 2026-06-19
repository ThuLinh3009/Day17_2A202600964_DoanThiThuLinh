# Day 17 Lab — Grading Rubric (100 pts core + 20 bonus)

Maps 1-to-1 with the deck's practical spine: Medallion gate/dedup (§2/§9),
the **agent-data flywheel** (§12 Thực Hành 1/3/4), and **complex RAG/KG** (§13).
Track-2 Daily Lab weight = 30%.

Everything is verifiable zero-key. Each criterion accepts evidence from the
`verify.py` output, `pytest`, or a printed run of the relevant entrypoint.

| # | Where | Criterion | Pts |
|---|---|---|---:|
| 1 | `main.py` / `verify.py` | Bronze loads all raw rows; Silver dedups on `order_id` (5 dropped) | 8 |
| 2 | `pipeline/validate.py` | Gate quarantines exactly 3 bad records to `quarantine.csv`; one bad row never halts the run | 10 |
| 3 | `main.py` | Gold aggregates **completed** orders by day; no duplicate `order_id` survives | 7 |
| 4 | `pipeline/dag.py` | Pipeline runs as a topologically-ordered DAG (deps respected) | 5 |
| 5 | `pipeline/streaming.py` | Partition-by-key topic + **idempotent** consumer (replayed event id ignored) | 8 |
| 6 | `dbt_project/` | `dbt build` passes (staging→gold + data tests + 1 unit test), Python ≤3.13 | 7 |
| 7 | `pipeline/traces.py` | Agent `gen_ai.*` span **trees** recursively flattened into Bronze (1 row/span) | 12 |
| 8 | `flywheel.py` | Per-trace summary rolls spans up to cost + latency + outcome | 6 |
| 9 | `pipeline/dataset.py` | Eval golden set curated from the **held-out** (`split='eval'`) traces | 6 |
| 10 | `pipeline/dataset.py` | DPO preference pairs `(prompt, chosen, rejected)` mined from ok-vs-error turns | 8 |
| 11 | `pipeline/dataset.py` | **Decontamination** drops every pair whose prompt overlaps the eval set | 8 |
| 12 | `pipeline/features.py` | `ASOF JOIN` gives point-in-time features; naive join is shown to **leak** the future | 10 |
| — | `verify.py` | Reproducible: `make setup && make verify` prints **ALL PASS** (16 checks) | 5 |
|   |   | **Core total** | **100** |

## Bonus Challenge (optional, 20 bonus pts)

**Open-ended brainstorm — no fixed task.** You pick a real-world data-pipeline
problem and brainstorm it into a design. See [`BONUS-CHALLENGE.md`](BONUS-CHALLENGE.md)
(Vietnamese default) / [`BONUS-CHALLENGE-EN.md`](BONUS-CHALLENGE-EN.md). Graded on
judgment, not a checklist — the points below describe what a strong write-up shows.

| Criterion | Pts |
|---|---:|
| `bonus/DESIGN.md` exists (≥ 600 words) on a real problem with a clear constraint set | 4 |
| 4–6 of the open questions answered, each with an **explicit tradeoff** (X vs Y, why X) | 8 |
| At least one **rejected alternative** named with a reason | 3 |
| An architecture sketch (ASCII or image) of the proposed pipeline | 2 |
| One decision shows Vietnamese-data, cost, or failure-semantics awareness | 3 |
|  | **Bonus total** | **20** |

A strong, well-reasoned brainstorm earns a written instructor review on judgment
and tradeoffs. A runnable prototype extending the lab is encouraged but not
required, and never the point — the reasoning is. Missing the bonus never lowers
your core grade.

## Submission

**No PR. Submit a public GitHub URL into the VinUni LMS Day-17 box.**

1. Push to `<your-username>/Day17-Track2-DataPipeline-Lab` (fork or fresh, **public**).
2. Include:
   - `verify.py` output (screenshot or pasted) showing **ALL PASS**
   - `pytest -q` output (18 passed)
   - `datasets/eval_golden.jsonl` + `datasets/preference_pairs.jsonl` (your generated artifacts)
   - `submission/REFLECTION.md` (≤ 200 words — see the prompt inside it)
   - **Optional:** `bonus/` folder for the bonus challenge
3. Paste the public repo URL into the LMS box. **Keep it public until grades release.** Private = 0.

## Late policy / regrade

Standard Track-2 policy applies — see `INDEX-Track2.md`.
