# Bonus Challenge — Day 17: Phiên Brainstorm Bài Toán Thực Tế (tùy chọn, +20đ)

> 🇬🇧 English: [`BONUS-CHALLENGE-EN.md`](BONUS-CHALLENGE-EN.md)

Lab lõi cho bạn một pipeline chạy được. Nhưng data engineering thật **không có
đề bài** — nó là phán đoán dưới sự mơ hồ. Bonus này **không phải một task định
sẵn**. Đây là một **phiên brainstorm**: bạn chọn một **bài toán pipeline dữ liệu
thực tế** (cho một sản phẩm AI) và brainstorm nó thành một thiết kế.

**Không có đáp án đúng duy nhất.** Bạn được chấm trên *chất lượng phán đoán*:
bạn đặt câu hỏi đúng chưa, bạn nêu đánh đổi rõ ràng chưa, bạn loại phương án sai
vì lý do gì.

---

## Bước 1 — Chọn một bài toán thực (open question)

Lấy một bài toán bạn **thật sự quan tâm** — từ công việc, từ một startup bạn muốn
xây, từ một dataset Việt Nam bạn biết. Nó phải đủ thật để có ràng buộc lộn xộn.

Vài *gợi ý mở* (không bắt buộc — bịa của riêng bạn còn tốt hơn):
- Ingest hàng nghìn **PDF hợp đồng/bệnh án/báo cáo** lộn xộn (scan, nhiều cột,
  bảng, tiếng Việt) thành dữ liệu có cấu trúc cho RAG.
- Xây **knowledge graph** từ kho văn bản pháp luật / tài liệu nội bộ để trả lời
  câu hỏi multi-hop.
- Pipeline **feature cho mô hình chống gian lận / chấm điểm tín dụng** — nơi rò
  rỉ point-in-time là thảm họa.
- **Flywheel** cho một chatbot CSKH: trace sản xuất → eval set + dữ liệu fine-tune.
- Clickstream **streaming** cho gợi ý real-time với ngân sách độ trễ chặt.
- Pipeline **chuẩn bị dữ liệu pretrain/SFT**: dedup, lọc chất lượng, decontaminate
  ở quy mô lớn.

---

## Bước 2 — Brainstorm bằng câu hỏi mở (đây là phần chính)

Tự phỏng vấn mình **từng câu một**. Đừng nhảy vào code. Những câu này chính là
các quyết định kỹ thuật thật mà lab đã chạm tới:

1. **Nguồn & hình dạng.** Dữ liệu đến từ đâu, dạng gì, bẩn cỡ nào? Schema có ổn
   định không, hay nó *trôi* (drift)?
2. **Batch hay streaming?** Độ tươi cần bao nhiêu là *đủ*? Lambda/Kappa, hay chỉ
   cần batch hằng đêm? Vì sao?
3. **Cái gì vỡ khi scale?** Ở 10×, 100× dữ liệu, bottleneck đầu tiên là gì?
   Small-files? Cost? Latency? Một con người trong vòng lặp?
4. **Hợp đồng & chất lượng.** Bạn validate gì *trước khi* dữ liệu vào model? Dòng
   xấu đi đâu? Ai được báo khi quarantine tăng vọt?
5. **Train/serve parity.** Feature lúc train có khớp lúc serve không? Chỗ nào có
   thể rò rỉ tương lai? Bạn cần point-in-time ở đâu?
6. **Phi cấu trúc → RAG hay KG?** Câu hỏi của bạn là lookup đơn giản (→ vector)
   hay multi-hop/tổng hợp toàn cục (→ graph)? Chi phí token/độ trễ của mỗi hướng?
7. **Flywheel.** Sản phẩm có sinh trace/feedback không? Làm sao biến nó thành eval
   set + dữ liệu train mà **không tự đầu độc** bằng leakage?
8. **Failure semantics.** Chạy lại có idempotent không? Side-effect không thể đảo
   ngược ở đâu? Backfill an toàn thế nào?
9. **Chi phí & vận hành.** Ai trả tiền cho pipeline này mỗi tháng? Đâu là 80% chi
   phí? Bạn cắt ở đâu mà không hại chất lượng?
10. **Bối cảnh Việt Nam.** Tiếng Việt có dấu, PDPL (Luật 91/2025), hạ tầng/băng
    thông — điều gì đổi so với một bài blog tiếng Anh?

> Không cần trả lời *hết* 10 câu. Chọn 4–6 câu **then chốt** với bài toán của bạn
> và đào sâu. Một câu trả lời thật, có đánh đổi, hơn mười câu hời hợt.

---

## Bước 3 — Sản phẩm nộp (`bonus/`)

1. **`bonus/DESIGN.md`** (≥ 600 từ) — phiên brainstorm của bạn, viết lại gọn:
   - Bài toán + ràng buộc thực (ai dùng, dữ liệu gì, vì sao khó).
   - 4–6 câu hỏi mở bạn chọn, mỗi câu kèm **quyết định + đánh đổi X vs Y, vì sao X**.
   - Ít nhất **một phương án bị loại**, nêu rõ lý do.
   - Một sơ đồ kiến trúc (ASCII/hình đều được).
2. **(Khuyến khích) một prototype tối thiểu** mở rộng lab này cho bài toán của bạn
   — ví dụ một stage mới trong `pipeline/`, hoặc một biến thể của flywheel/KG.
   Không cần hoàn chỉnh; cần *chạy được* và minh họa **một** quyết định cốt lõi.

Không có đáp án mẫu. Bản mạnh sẽ nhận **nhận xét viết tay của giảng viên** tập
trung vào phán đoán và lập luận đánh đổi. Bonus **không bao giờ** làm giảm điểm lõi.
