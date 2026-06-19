# Reflection — Day 17 (≤ 200 words)

**1. The flywheel.**
The most silently dangerous step is the `flatten()` recursion in `traces.py`. If a span tree has an unexpected nesting pattern (e.g., a missing `parent_id` or a child span tagged with `depth=0`), the recursive walk silently produces the wrong row count or wrong `trace_id` propagation — downstream `build_eval_set` will miss turns or duplicate them with no error raised. Detection: assert `n_spans >= len(traces)` in verify (done), plus a per-trace span-count monitor that alerts when the average drops below a historical baseline.

**2. Decontamination.**
Skipping it means the model trains on the exact prompts it will later be evaluated on. The eval loss drops artificially — the model memorizes the eval questions rather than generalising. The lie shows up as a large gap between held-out (real) eval metrics and internal dev-set metrics, and as suspiciously high exact-match scores on the eval set.

**3. Point-in-time.**
User `credit_score` in a loan-default model. At prediction time the credit score is the value known *before* loan origination; a naive join would attach the score *after* delinquency, leaking the outcome into the feature.

**4. Graph vs vector.**
Graph wins on: "Does a widget ship from the same warehouse as a gadget?" — requires joining two entity chains no single chunk contains. Vector wins on: "Summarise the returns policy" — a single dense chunk covers it entirely and graph traversal adds no value.
