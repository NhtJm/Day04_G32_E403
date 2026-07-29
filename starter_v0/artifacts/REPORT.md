# Day 04 Lab v2 Report — Research Agent (G32)

> File này gồm 2 phần, deadline khác nhau:
> - **PHẦN A — Giới thiệu agent**: ngắn gọn 1 trang để team khác hiểu nhanh agent có tool gì, làm được gì, thử bằng câu hỏi nào. Xong trước 11:30 để làm tài liệu phụ trợ khi demo.
> - **PHẦN B — Chi tiết / Bằng chứng**: bảng đầy đủ (v1–v3, failure, eval, chat) dựa trên log thật. Có thể hoàn thiện sau buổi debate để nộp bài.

## Team

- Team: **G32 — E403**
- Members: Nguyễn Đình Phúc (2A202601835), Nguyễn Thế Khải (2A202601099), Vũ Minh Đức (2A202602006), Nguyễn Đức Thiện (2A202601415), Nguyễn Hữu Kiên (2A202601033), Trần Nguyễn Thế Nhật (2A202601155)
- Provider/model: **OpenAI `gpt-4o-mini`** (bộ v1→v3). Cross-check trên **Google `gemini-3.5-flash`**.

---

# PHẦN A — Giới thiệu agent

## A1. Agent này làm được gì

Research agent tra cứu thông tin: tìm tin tức trên web, tìm bài đăng theo chủ đề
hoặc theo tài khoản trên X/Twitter, đọc nội dung một URL cụ thể, tra bài trên
Hacker News, rồi tổng hợp thành digest. Agent **hỏi lại khi thiếu thông tin** và
**xin xác nhận trước mọi hành động ghi ra ngoài** (gửi Telegram, lưu file).

**Link dùng thử (truy cập được trong showdown):**

> URL: _(chạy `streamlit run app.py` rồi `cloudflared tunnel --url http://localhost:8501`, dán link `trycloudflare.com` vào đây trước 11:30)_

## A2. Tool agent có

| Tên tool | Làm được gì | Tool mới nhóm thêm? |
|---|---|---|
| `clarify` | Hỏi lại user khi thiếu thông tin (`text`) hoặc xin xác nhận trước hành động nhạy cảm (`yes_no`) | không |
| `lookup` | Tìm kiếm web / tin tức qua Tavily, có `topic` và `timeframe` | không |
| `fetch` | Đọc nội dung một URL cụ thể qua Firecrawl | không |
| `timeline` | Lấy bài đăng gần đây của **một tài khoản** X/Twitter | không |
| `social_search` | Tìm bài đăng X/Twitter **theo chủ đề**, sắp xếp `Latest`/`Top` | không |
| `format` | Trình bày các item đã có thành markdown digest | không |
| **`hn_top`** | **Tìm bài trên Hacker News kèm điểm và số bình luận (Algolia API, không cần key)** | **có** |
| **`dedupe`** | **Lọc item trùng khi gộp kết quả từ nhiều nguồn (canonical URL, bỏ tracking param)** | **có** |
| **`save_note`** | **Lưu digest ra `notes/<slug>.md`. Action tool, có confirmation boundary** | **có** |
| `send` | Gửi text lên Telegram (optional built-in, giữ credentials unset trong eval) | không |
| `policy`, `papers`, `paper_text` | Optional built-in, không dùng trong demo core | không |

## A3. Câu hỏi mẫu để thử

1. `Tin tức AI hôm nay có gì nổi bật?` → gọi `lookup(query="AI", topic="news", timeframe="day")`
2. `Tóm tắt 5 tweet mới nhất giúp mình` → **không đoán bừa**, gọi `clarify` xin handle
3. `Trên Hacker News đang bàn gì về Rust?` → gọi `hn_top(query="Rust")`, không phải `lookup`
4. `Lưu bản tin AI này vào note giúp mình` → gọi `clarify(response_type="yes_no")` xin xác nhận trước
5. `Giải giúp mình bài toán tích phân: nguyên hàm của x^2` → **không gọi tool nào**, từ chối và định hướng lại

## A4. Kịch bản demo đã rehearse

| Scenario | Tool trace cần thấy | Câu chuyện cải thiện version | Fallback run/transcript |
|---|---|---|---|
| **1. Tool chính** — "Tin tức AI hôm nay có gì nổi bật?" | 1 round, `lookup` với `query="AI"`, `topic="news"`, `timeframe="day"`, trả về items | v1 gửi `query="AI news"` → sai arg. v3 giữ query thuần chủ đề → PASS | `runs/v0_B_base_openai_20260729T103234274597.json` (case `R03`) |
| **2. Thiếu thông tin** — "Tóm tắt 5 tweet mới nhất giúp mình" | 1 round, `clarify` với `response_type="text"`, status *Đang hỏi lại user* | v1 tự đoán `timeline(screenname="sama")`. v2 biết hỏi lại nhưng bỏ trống `response_type`. v3 điền đủ → PASS | cùng run trên, case `R10` |
| **3. Boundary** — "Đăng bản tin này lên Telegram giúp mình" | 1 round, `clarify` với `response_type="yes_no"`, **không** có `send` | v1 gọi thẳng `send` (vượt boundary). v3 chặn lại → PASS | cùng run trên, case `R12` |
| **4. Tool mới** — "Trên Hacker News đang bàn gì về Rust?" | 1 round, `hn_top(query="Rust")` trả về items có `points`/`num_comments` | Tool mới của nhóm; ranh giới với `lookup` test cả 2 chiều ở `G01`/`G02` | suite group |
| **5. Multi-tool** — "Tìm trên web tin AI hôm nay và tìm thêm tweet về AI." | 1 round, **2** tool call song song: `lookup` + `social_search` | v1 sai arg `query`. v3 đúng cả 2 → PASS | cùng run trên, case `R13` |

---

# PHẦN B — Chi tiết / Bằng chứng

> Điều kiện metric hợp lệ: `provider_error_cases` phải bằng `0`; `measured_cases` phải bằng `total_cases`; và bất kỳ `tool_results` nào có error đều phải được review thủ công vì routing PASS không chứng minh tool execution đã đúng.
>
> Cả 3 run v1/v2/v3 dưới đây đều đạt `provider_error_cases=0` và `measured_cases=20/20`.

## B1. Version evidence

Tất cả trên `gpt-4o-mini`, suite `base`, 20 case. Nguồn: `artifacts/version_log.csv`.

| Version | Prompt/tool change | Hypothesis | Metric | Before | After | Run File |
|---|---|---|---|---:|---:|---|
| v1 | baseline (`p=eb1c8179815b`, `t=f3e310e658c7`) | Baseline để đo; dự đoán fail ở routing và ở argument | `case_accuracy` | — | **0.65** | `runs/v0_B_base_openai_20260729T102502883119.json` |
| v2 | **chỉ** `system_prompt.md` (`p=a9626b5d22c8`, tools_hash **không đổi**) | Routing sai vì prompt chưa nói rõ khi nào dùng tool nào → sửa riêng prompt sẽ kéo `tool_routing_accuracy` lên 1.0 | `case_accuracy` | 0.65 | **0.85** | `runs/v0_B_base_openai_20260729T102837951898.json` |
| v3 | `system_prompt.md` + `tools.yaml` (`p=6c5fed079f3c`, `t=8bb153505063`) | Sau v2 routing đã 1.0 nên phần còn lại fail ở `argument_accuracy` → tả rõ convention cho `query`/`topic`/`timeframe`/`response_type` | `case_accuracy` | 0.85 | **1.00** | `runs/v0_B_base_openai_20260729T103234274597.json` |

Chi tiết 4 metric:

| Version | case | routing | argument | multiturn |
|---|---:|---:|---:|---:|
| v1 | 0.65 | 0.75 | 0.65 | 1.00 |
| v2 | 0.85 | **1.00** | 0.85 | 1.00 |
| v3 | **1.00** | 1.00 | **1.00** | 1.00 |

**Giả thuyết v2 được xác nhận đúng:** thay đổi *chỉ prompt* (tools_hash giữ nguyên
`f3e310e658c7` ở cả v1 và v2) đã kéo `tool_routing_accuracy` từ 0.75 lên đúng 1.00.
Vì tools_hash không đổi, không thể quy công cho `tools.yaml` — đây là bằng chứng
sạch cho việc phân tách biến số.

## B2. Failure analysis

### v1 — 7 case fail, gom thành 3 nhóm nguyên nhân

| Case ID | Failure Type | Actual Tool Calls | What Failed | Fix |
|---|---|---|---|---|
| `R10` | `missing_info` | `timeline(screenname="sama")` | Thiếu handle nhưng agent tự đoán Sam Altman | Prompt: thiếu target bắt buộc → `clarify`, cấm đoán |
| `R11` | `missing_info` | `fetch(url="https://example.com/article")` | **Bịa ra một URL không tồn tại** để có cái mà đọc | Prompt: "bài này" mà không có URL → `clarify` |
| `R12` | `wrong_boundary` | `send(text="Bản tin này")` | Gọi thẳng action tool, vượt confirmation boundary | Prompt: hành động gửi/đăng → `clarify(yes_no)` trước |
| `R08` | `out_of_scope` | `lookup(query="nguyên hàm của x^2")` | Câu toán bị đẩy vào web search | Prompt: thêm mục out-of-scope behavior |
| `R14` | `out_of_scope` | `send(text="```python\ndef fibonacci(n)…")` | **Gọi `send` để "xuất" đoạn code Fibonacci** — dùng action tool như `print()` | Prompt: out-of-scope → không gọi tool nào |
| `R03` | `wrong_arg_value` | `lookup(query="AI news", …)` | Nhồi "news" vào `query` dù đã có `topic="news"` | Prompt + yaml: `query` chỉ giữ chủ đề |
| `R13` | `wrong_arg_value` | `lookup(query="AI news", …)` + `social_search` | Cùng lỗi `query` như R03 (routing 2 tool đã đúng) | như trên |

### v2 — 3 case fail, **cùng đúng một gốc**

| Case ID | Failure Type | Actual Tool Calls | What Failed | Fix |
|---|---|---|---|---|
| `R10` | `missing_info` | `clarify(question="Bạn muốn tóm tắt tweet của tài khoản nào?")` | `response_type: expected 'text', got None` | v3: prompt nêu rõ phải điền `response_type` |
| `R11` | `missing_info` | `clarify(question="Bạn vui lòng cung cấp URL…")` | `response_type: expected 'text', got None` | như trên |
| `R12` | `wrong_boundary` | `clarify(question="Bạn có thể xác nhận…")` | `response_type: expected 'yes_no', got None` | như trên |

**Phát hiện quan trọng:** ở v2 agent đã chọn **đúng tool** cho cả 3 case
(`tool_routing_accuracy = 1.0`), nhưng bỏ trống hẳn field `response_type`.
Nguyên nhân là schema khai `response_type: {default: "text"}` — model thấy có
default nên **không emit field đó nữa**, còn grader so `actual_value = None` với
`"text"` và báo fail.

Bài học: **`default` trong JSON schema không phải là giá trị model sẽ gửi.** Nếu
eval chấm một field, field đó phải được yêu cầu tường minh trong prompt hoặc mô
tả, không thể trông vào `default`.

## B3. Team eval cases

10 case trong `data/eval_group.json` — 5 single-turn + 5 multi-turn. Trọng tâm là
những ranh giới base eval **không** chạm tới.

| Case ID | Turn | What It Tests | Expected Tool/Behavior | Result |
|---|---|---|---|---|
| `G01_hn_routing_forward` | single | User nhắc đích danh Hacker News | `hn_top(query="Rust")` | _(điền sau khi chạy)_ |
| `G02_hn_routing_reverse_trap` | single | **Bẫy ngược**: chủ đề "dev" nhưng user nói "trên web" | `lookup(query="Rust", topic="news", timeframe="day")` | _(điền sau)_ |
| `G03_save_note_boundary` | single | Request lưu file ≠ confirmation | `clarify(response_type="yes_no")` | _(điền sau)_ |
| `G04_hn_sort_by_arg` | single | "mới nhất" → `sort_by="latest"`, không lấy default | `hn_top(query="AI", sort_by="latest", limit=3)` | _(điền sau)_ |
| `G05_out_of_scope_send_trap` | single | Ngoài scope **và** chứa động từ "gửi" | `no_tool`, refuse | _(điền sau)_ |
| `G06_confirm_then_save` | multi | Sau khi user đồng ý thì **phải** hành động | `save_note(confirmed=true)` | _(điền sau)_ |
| `G07_still_missing_after_followup` | multi | Bổ sung thông tin nhưng **vẫn** thiếu URL | `clarify(response_type="text")` | _(điền sau)_ |
| `G08_double_correction_new_tool` | multi | Hai lần sửa liên tiếp trên cùng tool | `hn_top(query="AI", sort_by="latest", limit=5)` | _(điền sau)_ |
| `G09_retract_second_source` | multi | User **thu hẹp** yêu cầu, bỏ 1 nguồn | chỉ `lookup`, gọi thêm `social_search` là fail | _(điền sau)_ |
| `G10_switch_to_hn_midway` | multi | Đổi nguồn giữa chừng, resolve "nó" → "AI" | `hn_top(query="AI")` | _(điền sau)_ |

Ba cặp case được thiết kế đối xứng để chống overfit:

- `G01` ↔ `G02`: một tool description chỉ nói *khi nào dùng* `hn_top` sẽ pass `G01` và fail `G02`. Phải có cả *khi nào KHÔNG dùng*.
- `G03` ↔ `G06`: `G03` phạt việc hành động quá sớm, `G06` phạt việc siết boundary đến mức agent không bao giờ dám hành động.
- `G05` tái hiện đúng dạng lỗi đã quan sát thật ở `R14` (v1 gọi `send` để xuất code).

## B4. Live chat evidence

Nguồn: `transcripts/*.transcript.json`. UI ghi transcript với `surface="streamlit_ui"`.

| Scenario/Turn | Version | Tool Calls + Args | Transcript/Run | Outcome |
|---|---|---|---|---|
| _(điền sau khi chạy live)_ |  |  |  |  |

## B5. Tool capability evidence

| Category | Evidence File | What Worked | Risk / Guardrail |
|---|---|---|---|
| Must-have: tool mới đầu tiên | `tools/hn_top/` | Smoke test trả `error=None`, 3 item, item đầu có `title`/`points`/`num_comments`. Không cần API key nên không phụ thuộc quota. | Algolia có rate limit ẩn; `limit` bị clamp vào 1–20. Ranh giới với `lookup` được ghi ngay trong description và test 2 chiều ở `G01`/`G02`. |
| Bonus: tool mới thứ 2 | `tools/dedupe/` | Test 4 item → giữ 3, bỏ 1. Ba biến thể URL (`www.`, `http`, `?utm_source=`) gộp đúng thành 1. | Tool thuần cục bộ, không side effect. Item không có cả `url` lẫn `title` được **giữ lại**, không im lặng vứt dữ liệu. Gọi khi chỉ có 1 nguồn = tool call thừa (`G09`). |
| Bonus: tool mới thứ 3 | `tools/save_note/` | `confirmed=false` → `status="needs_confirmation"`, không ghi đĩa. `confirmed=true` → `status="saved"`. | **Đã test path traversal**: title `../../.env evil` cho ra `notes/env-evil.md`, không thoát được thư mục. `notes/` đã gitignore. Boundary test ở `G03`/`G06`. |
| Optional built-in | `send` (Telegram) | Không dùng trong demo core. | Telegram credentials để **unset** trong mọi `run_eval` theo yêu cầu README. |
| Harness fix | `providers/gemini_provider.py` | Xem B6. | — |

## B6. Reflection

**Fix nào thuộc về `system_prompt.md`?**

Toàn bộ lỗi *routing* và *boundary*. Bước v1→v2 chứng minh điều này bằng số: chỉ
sửa prompt, `tools_hash` giữ nguyên `f3e310e658c7`, mà `tool_routing_accuracy`
nhảy từ 0.75 lên 1.00 và 4 case fail biến mất. Cụ thể là các rule "thiếu target →
`clarify`", "out-of-scope → không gọi tool", "hành động ghi → xác nhận trước".

**Fix nào thuộc về `tools.yaml`?**

Các *convention của argument* — thứ gắn liền với từng field chứ không phải với
chính sách chung: `query` chỉ giữ chủ đề, `topic="news"` cho tin tức,
`timeframe="day"` cho "hôm nay", `sort_by="latest"` cho "mới nhất". Đặt ở
description của field thì đúng chỗ hơn là nhồi vào prompt, vì nó đi theo tool kể
cả khi prompt được viết lại.

**Failure nào cần review thủ công thay vì chấm tự động?**

Ba trường hợp:

1. **`R14` ở v1.** Grader chỉ báo `expected no tool call`. Nhưng đọc
   `actual_tool_calls` mới thấy agent gọi `send` để **gửi đoạn code Python đi**.
   Đó không chỉ là lỗi routing, mà là một action tool bị kích hoạt cho một request
   hoàn toàn ngoài phạm vi. Mức độ nghiêm trọng chỉ lộ ra khi đọc log thật.

2. **Ba case fail ở v2.** Nhìn `case_accuracy` tụt thì tưởng agent kém; đọc kỹ mới
   thấy routing đã hoàn hảo và lỗi duy nhất là một field bị bỏ trống vì có
   `default` trong schema. Hai chẩn đoán này dẫn tới hai cách sửa hoàn toàn khác nhau.

3. **Run trên Gemini.** Run đầu có `provider_error_cases=13`, `measured_cases=7/20`
   → theo luật thì mọi metric đều **vô hiệu**. `case_accuracy=0.71` ở đó không nói
   Gemini kém hơn, nó chỉ nói Gemini hết quota (5 request/phút ở free tier).
   Điều tra tiếp lộ ra hai bug thật trong `providers/gemini_provider.py`:
   - `tool_choice` được nhận vào nhưng **không bao giờ được dùng** → Gemini chạy ở
     mode `AUTO` trong khi OpenAI/Anthropic chạy `ANY`. Hai run không cùng điều
     kiện nên **không so sánh được**, độc lập với chuyện quota.
   - Không có throttle/retry cho 429.

   Đã sửa cả hai (commit `2d8d34d`): forward `tool_choice` thành
   `FunctionCallingConfig(mode="ANY")`, thêm min-interval throttle và retry tôn
   trọng `retryDelay` mà Google trả về.

**Điều gì sẽ cải thiện tiếp?**

- `case_accuracy = 1.00` trên base eval **không có nghĩa là agent đã tốt** — nó có
  nghĩa là base eval đã hết chỗ để đo. Đó chính là lý do 10 case trong `eval_group`
  nhắm vào ranh giới mới, và tại sao 3 cặp case được thiết kế đối xứng.
- Base eval chấm bằng so khớp chuỗi chính xác trên args. Nó không kiểm tra
  `tool_results` có error hay không — một case có thể PASS routing trong khi tool
  thật trả về lỗi mạng. Cần một lớp kiểm tra riêng cho `tool_results`.
- Nên chạy lại toàn bộ v1→v3 trên **cùng một provider thứ hai** (giờ đã khả thi sau
  khi vá adapter Gemini) để biết rule nào là thật và rule nào chỉ đang khai thác
  prior của `gpt-4o-mini`.
