"""Streamlit UI for the G32 research agent.

Reuses `run_model_tool_loop` from chat.py so the UI, the CLI and the eval all
drive the exact same agent loop against the same prompt/tool declarations.
Every turn is rendered as an inspectable trace and written to transcripts/.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from chat import (
    ROOT,
    ARTIFACTS_DIR,
    now_iso,
    run_model_tool_loop,
    safe_slug,
    trim_history,
    write_transcript,
)
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version

TRANSCRIPTS_DIR = ROOT / "transcripts"

# The three rehearsed demo scenarios: one straight tool call, one missing-info
# case, one sensitive-action case that must stop at the confirmation boundary.
SCENARIOS = {
    "1. Tool chính — tin tức web": "Tin tức AI hôm nay có gì nổi bật?",
    "2. Thiếu thông tin — phải hỏi lại": "Tóm tắt 5 tweet mới nhất giúp mình",
    "3. Boundary — hành động nhạy cảm": "Lưu bản tin AI này vào note giúp mình",
    "4. Tool mới — Hacker News": "Trên Hacker News đang bàn gì về Rust?",
    "5. Multi-tool — hai nguồn": "Tìm trên web tin AI hôm nay và tìm thêm tweet về AI.",
}

STATUS_STYLE = {
    "error": ("🔴", "Lỗi"),
    "needs_confirmation": ("🟡", "Chờ xác nhận"),
    "awaiting_user": ("🔵", "Đang hỏi lại user"),
    "ok": ("🟢", "OK"),
}


def classify(result: Any) -> str:
    """Map a raw tool result onto a display status."""
    if not isinstance(result, dict):
        return "ok"
    if result.get("error"):
        return "error"
    if result.get("awaiting_user"):
        return "awaiting_user"
    if result.get("status") == "needs_confirmation":
        return "needs_confirmation"
    return "ok"


def summarize(result: Any) -> str:
    """One-line gist of a tool result, so the trace is scannable without unfolding."""
    if not isinstance(result, dict):
        return str(result)[:160]
    if result.get("error"):
        return f"{result['error']}: {str(result.get('message', ''))[:120]}"
    items = result.get("items")
    if isinstance(items, list):
        first = items[0].get("title") if items and isinstance(items[0], dict) else None
        return f"{len(items)} item" + (f' — "{str(first)[:70]}"' if first else "")
    for key in ("question", "status", "path", "text"):
        if result.get(key):
            return f"{key}={str(result[key])[:120]}"
    return "(không có item)"


@st.cache_resource(show_spinner=False)
def get_provider(name: str):
    return make_provider(name)


def load_artifacts(prompt_path: Path, tools_path: Path):
    system_prompt = prompt_path.read_text(encoding="utf-8")
    declarations = load_tool_declarations(tools_path)
    return system_prompt, declarations, to_openai_tools(declarations)


def render_tool_event(event: dict[str, Any], key: str) -> None:
    result = event.get("result", {})
    status = classify(result)
    icon, label = STATUS_STYLE[status]
    name = event.get("tool", "?")
    args = event.get("args", {})

    with st.expander(f"{icon} `{name}` — {label} — {summarize(result)}", expanded=(status == "error")):
        left, right = st.columns(2)
        with left:
            st.caption("Arguments gửi cho tool")
            st.code(json.dumps(args, ensure_ascii=False, indent=2), language="json")
        with right:
            st.caption("Kết quả trả về")
            st.code(json.dumps(result, ensure_ascii=False, indent=2, default=str)[:4000], language="json")


def render_turn(turn: dict[str, Any], turn_key: str) -> None:
    rounds = turn.get("rounds", [])
    events = turn.get("tool_events", [])
    status = turn.get("status", "?")

    cols = st.columns(4)
    cols[0].metric("Status", status)
    cols[1].metric("Số round", len(rounds))
    cols[2].metric("Tool calls", len(events))
    cols[3].metric("Tool lỗi", sum(1 for e in events if classify(e.get("result")) == "error"))

    if not events:
        st.info("Agent trả lời trực tiếp, không gọi tool nào.")
        return

    for round_record in rounds:
        idx = round_record.get("round")
        calls = round_record.get("tool_calls", [])
        st.markdown(f"**Round {idx}** — {len(calls)} tool call: " + ", ".join(f"`{c['name']}`" for c in calls))
        if round_record.get("assistant_text"):
            st.caption(round_record["assistant_text"][:300])
        for i, event in enumerate(round_record.get("tool_results", [])):
            render_tool_event(event, f"{turn_key}_r{idx}_t{i}")


def main() -> None:
    st.set_page_config(page_title="G32 Research Agent", page_icon="🔎", layout="wide")

    with st.sidebar:
        st.header("⚙️ Cấu hình")
        provider_name = st.selectbox("Provider", ["gemini", "openai", "anthropic", "openrouter"])
        model = st.text_input("Model (để trống = mặc định)", value="") or None
        version = st.text_input("Version label", value="v3")
        max_rounds = st.slider("Max tool rounds", 1, 6, 4)
        history_window = st.slider("History window (số cặp lượt)", 0, 10, 5)

        st.divider()
        st.header("📌 Artifact đang chạy")
        prompt_path = Path(st.text_input("system_prompt", value=str(ARTIFACTS_DIR / "system_prompt.md")))
        tools_path = Path(st.text_input("tools.yaml", value=str(ARTIFACTS_DIR / "tools.yaml")))

        if not prompt_path.exists() or not tools_path.exists():
            st.error("Không tìm thấy file artifact.")
            st.stop()

        system_prompt, declarations, openai_tools = load_artifacts(prompt_path, tools_path)
        version_info = build_artifact_version(version, prompt_path, tools_path)
        st.code(version_info.artifact_version, language="text")
        st.caption(f"prompt_hash `{version_info.prompt_hash[:12]}` · tools_hash `{version_info.tools_hash[:12]}`")
        st.caption(
            "Đổi hai đường dẫn trên sang bản snapshot để chạy cùng một scenario "
            "trên version khác và so sánh trace."
        )

        st.divider()
        st.header(f"🧰 {len(declarations)} tool đã khai báo")
        for tool in declarations:
            st.markdown(f"**`{tool['name']}`** — {tool.get('description', '')[:110]}…")

    st.title("🔎 G32 Research Agent")
    st.caption("Cùng prompt, cùng tool declaration, cùng agent loop với eval và CLI.")

    if "history" not in st.session_state:
        st.session_state.history = []
        st.session_state.turns = []
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        st.session_state.transcript_id = f"{safe_slug(version)}_{safe_slug(provider_name)}_ui_{stamp}"

    transcript_path = TRANSCRIPTS_DIR / f"{st.session_state.transcript_id}.transcript.json"

    top = st.columns([3, 1])
    with top[0]:
        picked = st.selectbox("Kịch bản demo đã rehearse", ["— tự nhập —", *SCENARIOS])
    with top[1]:
        st.write("")
        st.write("")
        if st.button("🗑️ Xoá hội thoại", use_container_width=True):
            for key in ("history", "turns", "transcript_id"):
                st.session_state.pop(key, None)
            st.rerun()

    default_text = SCENARIOS.get(picked, "")
    user_text = st.chat_input("Nhập yêu cầu…") or (default_text if st.button("▶️ Chạy kịch bản đã chọn", disabled=not default_text) else None)

    for i, turn in enumerate(st.session_state.turns):
        with st.chat_message("user"):
            st.write(turn["user"])
        with st.chat_message("assistant"):
            st.write(turn.get("assistant_text") or turn.get("error", ""))
            with st.expander("🔬 Trace chi tiết", expanded=False):
                render_turn(turn, f"hist{i}")

    if user_text:
        with st.chat_message("user"):
            st.write(user_text)

        messages = [
            {"role": "system", "content": system_prompt},
            *trim_history(st.session_state.history, history_window),
            {"role": "user", "content": user_text},
        ]
        turn_record: dict[str, Any] = {
            "turn_index": len(st.session_state.turns) + 1,
            "started_at": now_iso(),
            "user": user_text,
            "status": "started",
            "rounds": [],
            "tool_events": [],
        }

        with st.chat_message("assistant"):
            try:
                with st.spinner("Agent đang chọn tool và chạy…"):
                    result = run_model_tool_loop(
                        provider=get_provider(provider_name),
                        messages=messages,
                        tools=openai_tools,
                        model=model,
                        max_tool_rounds=max_rounds,
                    )
                turn_record.update(result)
                st.write(result["assistant_text"])
                st.session_state.history.append({"role": "user", "content": user_text})
                st.session_state.history.append({"role": "assistant", "content": result["assistant_text"]})
            except Exception as exc:
                turn_record.update({"status": "provider_error", "error": f"{type(exc).__name__}: {exc}"})
                st.error(turn_record["error"])

            with st.expander("🔬 Trace chi tiết", expanded=True):
                render_turn(turn_record, "live")

        turn_record["ended_at"] = now_iso()
        st.session_state.turns.append(turn_record)

        write_transcript(transcript_path, {
            "transcript_id": st.session_state.transcript_id,
            **artifact_version_dict(version_info),
            "provider": provider_name,
            "model": model or getattr(get_provider(provider_name), "default_model", None),
            "system_prompt": str(prompt_path),
            "tools": str(tools_path),
            "surface": "streamlit_ui",
            "history_window": history_window,
            "max_tool_rounds": max_rounds,
            "created_at": st.session_state.turns[0]["started_at"],
            "turns": st.session_state.turns,
        })

    if st.session_state.turns:
        st.divider()
        st.caption(f"📝 Transcript: `{transcript_path.relative_to(ROOT)}`")
        st.download_button(
            "⬇️ Tải transcript JSON",
            data=transcript_path.read_text(encoding="utf-8"),
            file_name=transcript_path.name,
            mime="application/json",
        )


if __name__ == "__main__":
    main()
