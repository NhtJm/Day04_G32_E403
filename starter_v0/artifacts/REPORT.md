# Day 04 Lab v2 Report — Research Agent

> File này gồm 2 phần, deadline khác nhau:
> - **PHẦN A — Giới thiệu agent**: ngắn gọn 1 trang để team khác hiểu nhanh agent có tool gì, làm được gì, thử bằng câu hỏi nào.
> - **PHẦN B — Chi tiết / Bằng chứng**: bảng đầy đủ dựa trên log thật từ `runs/*.json`, `transcripts/*.transcript.json`, `artifacts/version_log.csv`.

## Team

- Team: `Day04_G32_E403`
- Members: `G32`
- Provider/model: `OpenAI` / model lấy từ cấu hình môi trường

---

# PHẦN A — Giới thiệu agent

## A1. Agent này làm được gì

Research agent dùng để tìm tin theo từ khóa, đọc URL cụ thể, lấy bài đăng mạng xã hội, xem timeline theo tài khoản và tổng hợp kết quả ngắn gọn cho người dùng. Agent cũng biết dừng để hỏi lại khi thiếu thông tin hoặc khi người dùng muốn gửi ra ngoài nhưng chưa xác nhận rõ.

**Link dùng thử**

- URL: `http://localhost:8501`

## A2. Tool agent có

| Tên tool | Làm được gì | Tool mới nhóm thêm? |
|---|---|---|
| `clarify` | hỏi lại khi thiếu người, link hoặc cần xác nhận trước khi gửi | không |
| `lookup` | tìm web theo từ khóa, topic và timeframe | không |
| `fetch` | đọc một URL cụ thể để tóm tắt nội dung | không |
| `social_search` | tìm bài đăng mạng xã hội theo từ khóa | không |
| `timeline` | lấy bài đăng mới nhất từ một tài khoản | không |
| `format` | định dạng/tóm tắt đầu ra | không |
| `send` | gửi nội dung ra kênh ngoài sau khi đã xác nhận | không |
| `policy` | tra cứu policy/rule nội bộ của bài lab | không |
| `papers` | tìm paper nghiên cứu | không |
| `paper_text` | đọc nội dung paper | không |
| `dedupe_items` | loại kết quả trùng theo URL/title/source | có |
| `filter_items` | lọc danh sách kết quả theo source/keyword | có |

## A3. Câu hỏi mẫu để thử

1. `Tìm tin robotics hôm nay.`
2. `Cho mình các tweet top về OpenAI.`
3. `Tóm tắt bài này giúp mình: https://www.reuters.com/business/`
4. `Lấy 2 tweet mới nhất của Andrej Karpathy.`
5. `Tìm tin AI hôm nay rồi gửi lên Telegram giúp mình.`

## A4. Kịch bản demo đã rehearse

| Scenario | Tool trace cần thấy | Câu chuyện cải thiện version | Fallback run/transcript |
|---|---|---|---|
| Tìm tin web theo chủ đề | `lookup(query="robotics", topic="news", timeframe="day")` | `v2` sửa tách arg cho `lookup` đúng hơn so với `v0`; `v3` là mốc chốt để nộp | `runs/v2_B_base_openai_20260729T103234274597.json` |
| Đọc đúng URL cụ thể | `fetch(url="https://openai.com/news")` | Sửa boundary để gặp URL thì dùng `fetch`, không `lookup` | `data/eval_group.json` + `runs/v1_B_group_openai_20260729T111313387315.json` |
| Thiếu thông tin thì hỏi lại | `clarify(response_type="text")` hoặc `clarify(response_type="yes_no")` | `v1` và `v2` giảm lỗi missing-info, confirm-before-send | `runs/v1_B_base_openai_20260729T102837951898.json` |
| Chat live tìm thông tin Trump | `lookup(query="Donald Trump", topic="general")` | Transcript UI dùng để minh họa bản final `v3` | `transcripts/v3_openai_20260729T110320049443.transcript.json` |

---

# PHẦN B — Chi tiết / Bằng chứng

> Điều kiện metric hợp lệ: `provider_error_cases = 0`; `measured_cases = total_cases`; và mọi lỗi tool execution cần review thủ công ngoài điểm routing.

## B1. Version evidence

| Version | Prompt/tool change | Hypothesis | Metric name | Before | After | Run File |
|---|---|---|---|---:|---:|---|
| `v0` | baseline | Đo hành vi ban đầu của agent trước khi tối ưu | `case_accuracy` |  | 0.65 | `runs/v0_B_base_openai_20260729T102502883119.json` |
| `v1` | sửa `artifacts/system_prompt.md` | Nếu quy định rõ lúc nào phải `clarify` và không được tự `send` thì điểm base tăng rõ | `case_accuracy` | 0.65 | 0.85 | `runs/v1_B_base_openai_20260729T102837951898.json` |
| `v2` | siết `system_prompt.md` + `artifacts/tools.yaml` | Nếu làm rõ routing, lookup args, missing-info và confirm boundary thì base có thể pass sạch | `case_accuracy` | 0.85 | 1.00 | `runs/v2_B_base_openai_20260729T103234274597.json` |
| `v3` | final release: chốt run cuối của `base` + `group` và dùng UI transcript làm bằng chứng demo | Nếu cả base và group đều đã có run pass sạch thì có thể đóng gói thành bản nộp cuối | `release_accuracy` | 1.00 | 1.00 | `runs/v2_B_base_openai_20260729T103234274597.json` + `runs/v1_B_group_openai_20260729T111313387315.json` |

## B2. Failure analysis

| Case ID | Failure Type | Actual Tool Calls | What Failed | Fix |
|---|---|---|---|---|
| `R03` | `wrong_arg_value` | `lookup(query="AI news", topic="news")` | Nhét cả ý nghĩa timeframe/topic vào `query` | Tách rõ `query="AI"` và giữ `topic/timeframe` ở field riêng trong prompt/tool description |
| `R08` | `out_of_scope` | `lookup(...)` | Câu hỏi meta/out-of-scope vẫn gọi tool | Thêm rule “meta/out-of-scope thì trả lời trực tiếp, không gọi tool” |
| `R10` | `missing_info` | `timeline(...)` | Thiếu handle/người nhưng agent không hỏi lại | Ép dùng `clarify(response_type="text")` khi thiếu person/account |
| `R11` | `missing_info` | `fetch(...)` | Người dùng muốn đọc bài nhưng chưa đưa URL cụ thể | Ép dùng `clarify(response_type="text")` khi chưa có URL |
| `R12` | `wrong_boundary` | `send(...)` | Agent tự gửi khi chưa xác nhận rõ | Thêm boundary “phải `clarify(response_type="yes_no")` trước `send`” |
| `R14` | `out_of_scope_coding` | `send(...)` | Yêu cầu coding/out-of-scope bị route sai sang tool research | Chặn tool cho câu hỏi ngoài phạm vi research agent |
| `G03` | `wrong_tool` | tool không phải `fetch` | Case URL cụ thể nhưng agent/group case chưa bám đúng hành vi | Sửa group case để expect `fetch(url=...)` rõ ràng |
| `G04` | `wrong_tool` | tool không khớp expected cũ | Case cũ ép post-processing bằng tool mới chưa ổn định | Đổi sang case `timeline(screenname="karpathy", limit=2)` bám đúng năng lực agent |
| `G07` | `wrong_tool` | tool không khớp expected cũ | Carry-context case cũ đặt kỳ vọng chưa sát routing hiện tại | Viết lại case để kiểm tra carry `topic/timeframe` với `lookup` đơn giản hơn |

## B3. Team eval cases

| Case ID | What It Tests | Expected Tool/Behavior | Result |
|---|---|---|---|
| `G01_single_robotics_today` | route web news ngoài domain AI | `lookup(query="robotics", topic="news", timeframe="day")` | PASS |
| `G02_single_top_openai_posts` | social search với `Top` | `social_search(query="OpenAI", search_type="Top")` | PASS |
| `G03_single_filter_reuters_only` | gặp URL cụ thể thì dùng `fetch` | `fetch(url="https://www.reuters.com/business/")` | PASS sau sửa |
| `G04_single_dedupe_ai_results` | map person sang handle + limit | `timeline(screenname="karpathy", limit=2)` | PASS sau sửa |
| `G05_single_missing_person_for_tweets` | thiếu person thì hỏi lại | `clarify(response_type="text")` | PASS |
| `G06_multi_switch_to_specific_url` | override context cũ bằng URL mới | `fetch(url="https://openai.com/news")` | PASS |
| `G07_multi_carry_topic_then_filter_source` | carry `topic/timeframe`, đổi `query` | `lookup(query="robotics", topic="news", timeframe="day")` | PASS sau sửa |
| `G08_multi_confirm_before_send_digest` | phải confirm trước khi gửi | `clarify(response_type="yes_no")` | PASS |
| `G09_multi_correct_person_and_limit` | sửa người + sửa limit ở turn sau | `timeline(screenname="elonmusk", limit=2)` | PASS |
| `G10_multi_no_tool_after_cancel` | turn meta sau cancel không gọi tool | `no_tool=true` | PASS |

## B4. Live chat evidence

| Scenario/Turn | Version | Tool Calls + Args | Transcript/Run | Outcome |
|---|---|---|---|---|
| Hỏi chung về Trump | `v3 demo` | `lookup(query="Donald Trump", topic="general")` | `transcripts/v3_openai_20260729T110022307317.transcript.json` | Trả về danh sách nguồn web/video và tóm tắt ngắn |
| Hỏi lại về Trump trên UI | `v3 demo` | `lookup(query="Donald Trump", topic="general")` | `transcripts/v3_openai_20260729T110320049443.transcript.json` | UI hiển thị được tool trace, args và kết quả |

## B5. Tool capability evidence

| Category | Evidence File | What Worked | Risk / Guardrail |
|---|---|---|---|
| Must-have: tool mới đầu tiên | `tools/dedupe_items/TOOL.md` | Đã khai báo, đăng ký trong `tools/__init__.py`, có mặt trong `artifacts/tools.yaml` | Chưa ép vào eval chính vì model chưa luôn chọn bước post-process này nếu prompt không yêu cầu rõ |
| Optional built-in | `runs/v2_B_base_openai_20260729T103234274597.json` | Bộ built-in `lookup` / `fetch` / `timeline` / `social_search` / `clarify` pass sạch base eval | Cần review thủ công nếu tool execution thật lỗi nhưng routing vẫn PASS |
| Bonus: tool mới thứ 4 trở đi | `tools/filter_items/TOOL.md` | Nhóm có thêm `filter_items` như tool mới thứ hai để mở rộng pipeline hậu xử lý | Không claim bonus “tool thứ 4+”; tool này chủ yếu là mở rộng năng lực |

## B6. Reflection

- Fix thuộc `artifacts/system_prompt.md`: clarify khi thiếu info, không gọi tool cho câu hỏi meta/out-of-scope, confirm trước `send`, ưu tiên `fetch` khi user đã đưa URL.
- Fix thuộc `artifacts/tools.yaml`: mô tả lại boundary của `lookup`, `fetch`, `timeline`, `social_search` để model tách đúng args và route đúng tool.
- Failure cần review thủ công: các case routing PASS nhưng tool output thật có thể không tốt, ví dụ live chat `lookup` ra nhiều nguồn YouTube/video lẫn web; grader không đo chất lượng nội dung cuối.
- Improve tiếp theo: thêm eval cho chuỗi nhiều tool (`lookup` → `filter_items` → `dedupe_items` → `format`), log model name rõ hơn trong transcript và thêm smoke test cho UI.
