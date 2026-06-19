# Lab 17 — Data Pipeline Engineering (Track 2)

> 🇬🇧 English version: [`README_en.md`](README_en.md)

Xây một data pipeline **chạy thật** cho dữ liệu **AI** — không chỉ là Medallion
ETL, mà là **flywheel dữ liệu của agent**: biến chính traffic của agent thành
dataset eval và fine-tuning để agent ngày càng tốt hơn.

```
raw orders  ─▶ ingest ─▶ validate(gate) ─▶ dedup→Gold ─▶ load        (Medallion lõi)
agent traces ─▶ Bronze spans ─▶ eval set + DPO pairs ─▶ point-in-time features  (flywheel)
docs ─▶ chunk→embed (vector)   |   docs ─▶ triples→graph (knowledge graph)       (RAG/KG)
```

Mọi thứ chạy **zero-key, đa nền tảng** trên DuckDB + Python thuần. **Đường lite**
chỉ cần `pip install`. Docker và dbt là tùy chọn.

Lab này trả thẳng vào bài giảng:
- seed orders có **~30% trùng lặp + 3 dòng hỏng** → dedup ở Silver, cách ly
  (quarantine) dòng xấu để model không bao giờ thấy chúng (§2/§9);
- **agent traces** mẫu chứa cả thành công *lẫn* thất bại → tạo eval set và
  **cặp ưu tiên DPO**, kèm **decontamination** để không bao giờ train trên thứ
  bạn dùng để chấm (§12 Thực Hành 1/3/4);
- phép join feature ngây thơ **rò rỉ tương lai** → sửa bằng `ASOF` point-in-time
  join (§11 training-serving skew).

---

## Bắt đầu nhanh (đường lite — phần chấm điểm)

```bash
make setup          # python -m venv .venv + cài đặt (hoặc làm tay, xem dưới)
make verify         # smoke test end-to-end — kỳ vọng "ALL PASS" (16 checks)
make run            # pipeline Medallion: dedup + quarantine + Gold
make flywheel       # agent traces -> Bronze -> dataset eval/DPO + PIT features
make kg             # bonus: knowledge graph từ docs
make test           # pytest (18 tests)
```

Không dùng `make`:

```bash
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python verify.py && python main.py && python flywheel.py && python kg_demo.py
pytest -q
```

> **Phiên bản Python:** đường lite chạy trên **Python 3.10+** (đã test 3.14).
> **Track dbt cần Python 3.10–3.13** — dbt chưa hỗ trợ 3.14.

---

## Có gì trong hộp

| Track | File | Bạn học gì |
|---|---|---|
| **T1 Medallion ETL/ELT** | `pipeline/extract.py`, `transform.py` | Bronze (raw, append-only) → Silver (typed, **deduped**) → Gold (features) trên DuckDB |
| **T2 Orchestration** | `pipeline/dag.py`, `main.py` | DAG runner Python thuần (thứ tự topo, deps) — hình dạng của Airflow mà không nặng nề |
| **T3 Quality gate** | `pipeline/validate.py` | Pandera schema-as-contract; **quarantine / DLQ** cho dòng xấu; `lazy=True` gom mọi lỗi |
| **T4 dbt** | `dbt_project/` | dbt-duckdb staging→gold, test `not_null`/`unique` **+ 1 unit test** cho logic dedup |
| **T5 Streaming** | `pipeline/streaming.py` | Topic partition-by-key + consumer **idempotent** (dedup theo event id) — ý tưởng lõi của Kafka, không cần broker |
| **T6 Agent flywheel** | `pipeline/traces.py`, `flywheel.py` | **Làm phẳng cây span `gen_ai.*` vào Bronze** — hành vi của agent trở thành dữ liệu |
| **T7 Curate dataset** | `pipeline/dataset.py` | Eval golden set + **cặp DPO `(prompt, chosen, rejected)`** từ lượt ok-vs-error, kèm **decontamination** |
| **T8 Point-in-time features** | `pipeline/features.py` | **`ASOF JOIN`** của DuckDB cho train/serve parity; join ngây thơ bị chỉ ra là **rò rỉ tương lai** |
| **Bonus RAG** | `pipeline/embed.py` | unstructured → recursive chunk → embedding → store (hash embedder zero-key) |
| **Bonus KG** | `pipeline/kg.py`, `kg_demo.py` | docs → bộ ba (entity, relation, entity) **→ graph → traversal 2-hop thật**, đối lập vector foil không nối được fact bị tách (§13) |
| **Bonus Docker** | `docker/` | Cùng pipeline trên **Airflow 3 + Redpanda thật** |

---

## Flywheel dữ liệu của agent (T6–T8) — trái tim của lab

Ngày 13 đã gắn telemetry cho agent tích lũy và xuất ra một **trace mỗi lượt**:
cây span lồng nhau (`invoke_agent` → `retrieve_policy` → `chat`) với thuộc tính
OpenTelemetry `gen_ai.*`. `data/traces/agent_traces.json` là một mẫu đúng như
bản xuất đó (có lượt thành công, có lượt lỗi `ToolError`, `Refusal`,
`Hallucination`).

1. **`traces.py` — trace → Bronze.** `flatten()` đệ quy cây span thành một dòng
   phẳng cho mỗi span (mẹo biến cây thành thứ truy vấn được). `traces_to_bronze`
   đổ vào append-only; `trace_summary` gộp mỗi trace thành cost + latency + kết quả.
2. **`dataset.py` — Bronze → dataset.** `build_eval_set` lấy **phần holdout được
   curate** (`split='eval'`) trong các lượt thành công làm benchmark.
   `build_preference_pairs` khai thác bộ ba `(prompt, chosen, rejected)` bằng cách
   ghép một câu trả lời tốt với một câu trả lời lỗi cho **cùng một câu hỏi**.
   `decontaminate` sau đó **bỏ mọi cặp có prompt nằm trong eval set** — trên seed,
   3 cặp thô → **1 cặp sạch (bỏ 2)**. Bỏ qua bước này là cách số 1 khiến eval
   nói dối âm thầm.
3. **`features.py` — point-in-time correctness.** `point_in_time_features` dùng
   `ASOF JOIN` để mỗi event chỉ thấy giá trị feature đã biết *tại hoặc trước* nó;
   `naive_leaky_features` cho thấy join "giá trị mới nhất" rò rỉ `lifetime_spend`
   tương lai vào dòng training.

Dataset đầu ra nằm ở `datasets/`, sẵn sàng cho **Ngày 22** (SFT/DPO). Đó chính là
vòng lặp: Ngày 13 sinh trace → **Ngày 17 biến chúng thành dữ liệu** → Ngày 22 train.

---

## Gate + dedup hoạt động thế nào (T1–T3)

`data/raw_orders.csv` có order thật, **5 dòng trùng y hệt** (order_id 1–5 mỗi cái
xuất hiện 2 lần), và **3 dòng xấu** — `user_id` null, `amount` âm, và `status`
ngoài từ vựng.

1. **Extract** → Bronze, nguyên vẹn. Không sửa; nguồn-sự-thật dựng lại được.
2. **Validate** → Pandera tách clean vs xấu; dòng xấu → `quarantine.csv` (DLQ).
   Một dòng xấu không bao giờ làm dừng cả run.
3. **Transform** → Silver dedup theo `order_id`; Gold gộp order **completed** theo ngày.

`verify.py` kiểm chứng tất cả (16 checks): dedup, đúng 3 quarantine, không còn
`order_id` trùng, streaming idempotent, embedding ingestion, **trace→Bronze
flatten, curate eval/DPO, decontamination, chống rò rỉ ASOF, và knowledge graph**.

---

### Track dbt (tùy chọn, Python ≤ 3.13)

```bash
python3.13 -m venv .venv-dbt && . .venv-dbt/bin/activate
pip install -r requirements-dbt.txt
cd dbt_project && DBT_PROFILES_DIR=. dbt build      # seed → run → test (kỳ vọng PASS=11)
```

### Bonus Docker (tùy chọn)

```bash
docker compose -f docker/docker-compose.yml up      # Airflow UI tại http://localhost:8080
```

---

## Bài tập mở rộng (không chấm, để đào sâu)

0. **Decontamination mờ (fuzzy)**: `dataset.decontaminate` chỉ khớp chính xác —
   một prompt eval viết lại vẫn rò rỉ. Thêm khớp n-gram (13-gram) hoặc tương đồng
   embedding (tái dùng `embed.py`) và chứng minh một bản viết lại bị loại (§12).
1. **Embeddings thật**: thay hash embedder trong `embed.py` bằng model
   sentence-transformers local; thêm re-embed tăng dần theo content hash để chỉ
   embed lại chunk đã đổi (§3).
2. **LLM trích KG**: thay extractor tất định trong `kg.py` bằng LLM + entity
   resolution (§13).
3. **Data contract**: viết `datacontract.yaml` (ODCS) cho bảng orders và nối
   `datacontract test` vào một bước CI (§10).
4. **An toàn backfill**: làm `main.py` idempotent khi chạy lặp, thêm cửa sổ
   backfill `--date` (§14). Chứng minh chạy lại không nhân đôi dòng.

Observability, lineage, anomaly detection cho pipeline này là **Ngày 27**; định
dạng bảng lakehouse nó hạ cánh là **Ngày 18**; vector/feature store nó nuôi là
**Ngày 19**.

---

## Chấm điểm & nộp bài

Xem [`rubric.md`](rubric.md) (100 lõi + 20 bonus) và
[`submission/REFLECTION.md`](submission/REFLECTION.md). Nộp một **URL GitHub
public** vào ô LMS Ngày 17 — không PR. Mới với workflow lập trình cùng AI? Đọc
[`VIBE-CODING.md`](VIBE-CODING.md) trước. Bonus là một **phiên brainstorm mở** về
bài toán thực tế — xem [`BONUS-CHALLENGE.md`](BONUS-CHALLENGE.md).
