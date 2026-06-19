# Bonus Challenge — Day 17: A Brainstorm Session on Real-World Problems (optional, +20 pts)

> 🇻🇳 Tiếng Việt (mặc định): [`BONUS-CHALLENGE.md`](BONUS-CHALLENGE.md)

The core lab hands you a working pipeline. But real data engineering **has no
problem statement** — it's judgment under ambiguity. This bonus is **not a fixed
task**. It's a **brainstorm session**: you pick a **real-world data-pipeline
problem** (for an AI product) and brainstorm it into a design.

**There is no single right answer.** You're graded on *quality of judgment*: did
you ask the right questions, did you name the tradeoffs explicitly, did you
reject the wrong option for a stated reason.

---

## Step 1 — Pick a real problem (open question)

Take a problem you **actually care about** — from work, from a startup you'd like
to build, from a Vietnamese dataset you know. It has to be real enough to carry
messy constraints.

A few *open seeds* (not requirements — your own is better):
- Ingest thousands of messy **contract / medical / report PDFs** (scanned,
  multi-column, tables, Vietnamese) into structured data for RAG.
- Build a **knowledge graph** from a legal-text or internal-docs corpus to answer
  multi-hop questions.
- A **feature pipeline for a fraud / credit-scoring model** — where point-in-time
  leakage is catastrophic.
- A **flywheel** for a customer-support chatbot: production traces → eval set +
  fine-tuning data.
- **Streaming** clickstream for real-time recommendations under a tight latency budget.
- A **pretraining/SFT data-prep** pipeline: dedup, quality filtering, decontamination at scale.

---

## Step 2 — Brainstorm with open questions (this is the heart)

Interview yourself **one question at a time**. Don't jump to code. These are the
real engineering decisions the lab touched:

1. **Source & shape.** Where does the data come from, what form, how dirty? Is the
   schema stable, or does it *drift*?
2. **Batch or streaming?** How fresh is *fresh enough*? Lambda/Kappa, or is a
   nightly batch fine? Why?
3. **What breaks at scale?** At 10×, 100× the data, what's the first bottleneck —
   small files? Cost? Latency? A human in the loop?
4. **Contracts & quality.** What do you validate *before* data reaches the model?
   Where do bad rows go? Who gets paged when quarantine spikes?
5. **Train/serve parity.** Do training features match serving features? Where
   could the future leak in? Where do you need point-in-time?
6. **Unstructured → RAG or KG?** Is your question a simple lookup (→ vector) or
   multi-hop / global summary (→ graph)? What's the token/latency cost of each?
7. **Flywheel.** Does the product emit traces/feedback? How do you turn it into an
   eval set + training data **without poisoning yourself** with leakage?
8. **Failure semantics.** Is a re-run idempotent? Where are the irreversible
   side-effects? How is a backfill made safe?
9. **Cost & operations.** Who pays for this pipeline monthly? Where's 80% of the
   cost? Where can you cut without hurting quality?
10. **Vietnamese context.** Accented Vietnamese, PDPL (Law 91/2025), infra /
    bandwidth — what changes versus an English blog post?

> You don't have to answer *all 10*. Pick the **4–6 that are load-bearing** for
> your problem and go deep. One real answer with a tradeoff beats ten shallow ones.

---

## Step 3 — Deliverable (`bonus/`)

1. **`bonus/DESIGN.md`** (≥ 600 words) — your brainstorm, written up tightly:
   - The problem + real constraints (who uses it, what data, why it's hard).
   - The 4–6 open questions you chose, each with a **decision + tradeoff X vs Y,
     why X**.
   - At least **one rejected alternative**, with the reason.
   - One architecture sketch (ASCII or image both fine).
2. **(Encouraged) a minimal prototype** extending this lab toward your problem —
   e.g. a new stage in `pipeline/`, or a variant of the flywheel/KG. It needn't be
   complete; it must *run* and illustrate **one** core decision.

There's no answer key. A strong submission earns a **written instructor review**
focused on judgment and tradeoff reasoning. The bonus **never** lowers your core grade.
