from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from chat import ROOT, now_iso, run_model_tool_loop, safe_slug, trim_history, write_transcript
from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version


ARTIFACTS_DIR = ROOT / "artifacts"
RUNS_DIR = ROOT / "runs"
TRANSCRIPTS_DIR = ROOT / "transcripts"
SYSTEM_PROMPT_PATH = ARTIFACTS_DIR / "system_prompt.md"
TOOLS_PATH = ARTIFACTS_DIR / "tools.yaml"

load_lab_env(ROOT)


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def ensure_dirs() -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)


def init_session() -> None:
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "turns" not in st.session_state:
        st.session_state.turns = []
    if "transcript_path" not in st.session_state:
        st.session_state.transcript_path = None
    if "transcript" not in st.session_state:
        st.session_state.transcript = None
    if "last_error" not in st.session_state:
        st.session_state.last_error = None


def build_transcript(version: str, provider_name: str, model: str | None, history_window: int, max_tool_rounds: int) -> tuple[dict[str, Any], Path]:
    artifact_version = build_artifact_version(version, SYSTEM_PROMPT_PATH, TOOLS_PATH)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    transcript_id = "_".join([safe_slug(version), safe_slug(provider_name), timestamp])
    transcript_path = TRANSCRIPTS_DIR / f"{transcript_id}.transcript.json"
    transcript = {
        "transcript_id": transcript_id,
        **artifact_version_dict(artifact_version),
        "provider": provider_name,
        "model": model,
        "system_prompt": str(SYSTEM_PROMPT_PATH),
        "tools": str(TOOLS_PATH),
        "history_window": history_window,
        "max_tool_rounds": max_tool_rounds,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "turns": [],
    }
    return transcript, transcript_path


def reset_session(version: str, provider_name: str, model: str | None, history_window: int, max_tool_rounds: int) -> None:
    transcript, transcript_path = build_transcript(version, provider_name, model, history_window, max_tool_rounds)
    st.session_state.chat_history = []
    st.session_state.turns = []
    st.session_state.transcript = transcript
    st.session_state.transcript_path = transcript_path
    st.session_state.last_error = None
    write_transcript(transcript_path, transcript)


def ensure_transcript(version: str, provider_name: str, model: str | None, history_window: int, max_tool_rounds: int) -> None:
    if st.session_state.transcript is None or st.session_state.transcript_path is None:
        reset_session(version, provider_name, model, history_window, max_tool_rounds)


def render_tool_event(event: dict[str, Any], round_index: int, event_index: int) -> None:
    result = event.get("result")
    has_error = bool(isinstance(result, dict) and result.get("error"))
    status = "error" if has_error else ("awaiting_user" if isinstance(result, dict) and result.get("awaiting_user") else "ok")
    with st.expander(f"Round {round_index} • {event_index}. `{event.get('tool')}` • {status}", expanded=has_error):
        st.code(json_text(event.get("args", {})), language="json")
        st.code(json_text(result), language="json")


def render_chat_turn(turn: dict[str, Any]) -> None:
    with st.chat_message("user"):
        st.markdown(turn["user"])
    with st.chat_message("assistant"):
        st.markdown(turn.get("assistant_text") or "_No response_")
        if turn.get("status") == "provider_error":
            st.error(turn.get("error", "Unknown provider error"))
        rounds = turn.get("rounds", [])
        if rounds:
            st.caption(f"Tool rounds: {len(rounds)}")
        for round_record in rounds:
            tool_results = round_record.get("tool_results", [])
            if not tool_results:
                continue
            st.markdown(f"**Round {round_record.get('round')} trace**")
            for idx, event in enumerate(tool_results, start=1):
                render_tool_event(event, round_record.get("round", 0), idx)


def run_live_turn(
    *,
    provider_name: str,
    model: str | None,
    version: str,
    history_window: int,
    max_tool_rounds: int,
    user_text: str,
) -> None:
    ensure_transcript(version, provider_name, model, history_window, max_tool_rounds)
    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    tool_declarations = load_tool_declarations(TOOLS_PATH)
    openai_tools = to_openai_tools(tool_declarations)
    provider = make_provider(provider_name)

    turn_index = len(st.session_state.turns) + 1
    messages = [
        {"role": "system", "content": system_prompt},
        *trim_history(st.session_state.chat_history, history_window),
        {"role": "user", "content": user_text},
    ]

    turn_record: dict[str, Any] = {
        "turn_index": turn_index,
        "started_at": now_iso(),
        "user": user_text,
        "status": "started",
        "assistant_text": None,
        "rounds": [],
        "tool_events": [],
    }

    try:
        result = run_model_tool_loop(
            provider=provider,
            messages=messages,
            tools=openai_tools,
            model=model,
            max_tool_rounds=max_tool_rounds,
        )
        turn_record.update(result)
        assistant_text = result["assistant_text"]
        st.session_state.chat_history.append({"role": "user", "content": user_text})
        st.session_state.chat_history.append({"role": "assistant", "content": assistant_text})
        st.session_state.last_error = None
    except Exception as exc:
        turn_record.update({
            "status": "provider_error",
            "assistant_text": f"Provider error: {type(exc).__name__}: {exc}",
            "error": f"{type(exc).__name__}: {exc}",
        })
        st.session_state.last_error = turn_record["error"]

    turn_record["ended_at"] = now_iso()
    st.session_state.turns.append(turn_record)
    st.session_state.transcript["turns"].append(turn_record)
    write_transcript(st.session_state.transcript_path, st.session_state.transcript)


def read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def run_files() -> list[Path]:
    return sorted(RUNS_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)


def transcript_files() -> list[Path]:
    return sorted(TRANSCRIPTS_DIR.glob("*.transcript.json"), key=lambda item: item.stat().st_mtime, reverse=True)


def render_run_explorer() -> None:
    st.subheader("Run Explorer")
    files = run_files()
    if not files:
        st.info("Chưa có run JSON nào.")
        return
    selected = st.selectbox("Chọn run JSON", files, format_func=lambda item: item.name, key="run_explorer_file")
    payload = read_json_file(selected)
    if not payload:
        st.error("Không đọc được run JSON.")
        return

    summary = payload.get("summary", {})
    cols = st.columns(5)
    cols[0].metric("Case accuracy", summary.get("case_accuracy"))
    cols[1].metric("Routing", summary.get("tool_routing_accuracy"))
    cols[2].metric("Args", summary.get("argument_accuracy"))
    cols[3].metric("Provider errors", summary.get("provider_error_cases"))
    cols[4].metric("Passed", f"{summary.get('passed_cases')}/{summary.get('total_cases')}")

    st.caption(
        f"run_id={payload.get('run_id')} • artifact_version={payload.get('artifact_version')} • "
        f"prompt_hash={str(payload.get('prompt_hash', ''))[:12]} • tools_hash={str(payload.get('tools_hash', ''))[:12]}"
    )
    st.json(summary)

    results = payload.get("results", [])
    selected_case_id = st.selectbox("Chọn case", [item.get("id") for item in results], key="run_case_id")
    case = next((item for item in results if item.get("id") == selected_case_id), None)
    if not case:
        return

    st.markdown(f"**Input**")
    if case.get("is_multiturn"):
        st.code(json_text(case.get("input")), language="json")
    else:
        st.write(case.get("input"))
    st.markdown("**Expected**")
    st.code(json_text(case.get("expect")), language="json")
    st.markdown("**Observed**")
    st.code(json_text(case.get("result")), language="json")
    st.markdown("**Tool results**")
    st.code(json_text(case.get("tool_results", [])), language="json")


def render_version_compare() -> None:
    st.subheader("Version Compare")
    files = run_files()
    if len(files) < 2:
        st.info("Cần ít nhất 2 run JSON để so sánh.")
        return

    left_col, right_col = st.columns(2)
    left_file = left_col.selectbox("Run A", files, format_func=lambda item: item.name, key="compare_left")
    right_file = right_col.selectbox("Run B", files, index=1 if len(files) > 1 else 0, format_func=lambda item: item.name, key="compare_right")

    left_payload = read_json_file(left_file)
    right_payload = read_json_file(right_file)
    if not left_payload or not right_payload:
        st.error("Không đọc được một trong hai run JSON.")
        return

    common_case_ids = sorted(set(item.get("id") for item in left_payload.get("results", [])) & set(item.get("id") for item in right_payload.get("results", [])))
    if not common_case_ids:
        st.info("Không có case chung giữa hai run.")
        return

    selected_case_id = st.selectbox("Scenario / Case ID", common_case_ids, key="compare_case")
    left_case = next(item for item in left_payload["results"] if item.get("id") == selected_case_id)
    right_case = next(item for item in right_payload["results"] if item.get("id") == selected_case_id)

    st.caption(f"Comparing `{selected_case_id}` across artifact versions.")
    col_a, col_b = st.columns(2)
    for col, label, payload, case in [
        (col_a, "Run A", left_payload, left_case),
        (col_b, "Run B", right_payload, right_case),
    ]:
        with col:
            st.markdown(f"**{label}: {payload.get('artifact_version')}**")
            st.write(f"Passed: `{case.get('result', {}).get('passed')}`")
            st.code(json_text(case.get("result", {}).get("actual_tool_calls", [])), language="json")
            st.code(json_text(case.get("result", {}).get("failures", [])), language="json")


def render_transcript_browser() -> None:
    st.subheader("Transcript Browser")
    files = transcript_files()
    if not files:
        st.info("Chưa có transcript nào.")
        return
    selected = st.selectbox("Chọn transcript", files, format_func=lambda item: item.name, key="transcript_browser_file")
    payload = read_json_file(selected)
    if not payload:
        st.error("Không đọc được transcript.")
        return

    st.caption(
        f"transcript_id={payload.get('transcript_id')} • artifact_version={payload.get('artifact_version')} • "
        f"provider={payload.get('provider')} • model={payload.get('model')}"
    )
    st.json({
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
        "turn_count": len(payload.get("turns", [])),
        "prompt_hash": payload.get("prompt_hash"),
        "tools_hash": payload.get("tools_hash"),
    })
    for turn in payload.get("turns", []):
        render_chat_turn(turn)


def main() -> None:
    ensure_dirs()
    init_session()

    st.set_page_config(page_title="Research Agent UI", layout="wide")
    st.title("Research Agent UI")
    st.caption("Chat, tool trace, transcript, run explorer, and version comparison in one place.")

    with st.sidebar:
        st.header("Session")
        provider_name = st.selectbox("Provider", ["openai", "openrouter", "anthropic", "gemini"], index=0)
        version = st.text_input("Version", value="v3")
        model = st.text_input("Model override", value="")
        history_window = st.number_input("History window", min_value=1, max_value=10, value=5)
        max_tool_rounds = st.number_input("Max tool rounds", min_value=1, max_value=8, value=4)
        if st.button("New Session", use_container_width=True):
            reset_session(version, provider_name, model or None, int(history_window), int(max_tool_rounds))
            st.rerun()

        ensure_transcript(version, provider_name, model or None, int(history_window), int(max_tool_rounds))
        transcript = st.session_state.transcript
        st.markdown("**Current Metadata**")
        st.caption(f"artifact_version: `{transcript['artifact_version']}`")
        st.caption(f"prompt_hash: `{transcript['prompt_hash'][:12]}`")
        st.caption(f"tools_hash: `{transcript['tools_hash'][:12]}`")
        st.caption(f"transcript_id: `{transcript['transcript_id']}`")
        st.caption(f"transcript_file: `{st.session_state.transcript_path.name}`")
        st.caption("Cloudflare Tunnel: `cloudflared tunnel --url http://localhost:8501`")

    tab_chat, tab_runs, tab_compare, tab_transcripts = st.tabs([
        "Live Chat",
        "Run Explorer",
        "Version Compare",
        "Transcript Browser",
    ])

    with tab_chat:
        top_col, side_col = st.columns([2, 1])
        with top_col:
            st.subheader("Scenario Chat")
            for turn in st.session_state.turns:
                render_chat_turn(turn)
            prompt = st.chat_input("Nhập request để chạy agent")
            if prompt:
                run_live_turn(
                    provider_name=provider_name,
                    model=model or None,
                    version=version,
                    history_window=int(history_window),
                    max_tool_rounds=int(max_tool_rounds),
                    user_text=prompt,
                )
                st.rerun()
        with side_col:
            st.subheader("Current Transcript")
            transcript = st.session_state.transcript
            st.json({
                "transcript_id": transcript.get("transcript_id"),
                "artifact_version": transcript.get("artifact_version"),
                "provider": transcript.get("provider"),
                "model": transcript.get("model"),
                "turn_count": len(transcript.get("turns", [])),
                "updated_at": transcript.get("updated_at"),
            })
            if st.session_state.last_error:
                st.error(st.session_state.last_error)
            st.download_button(
                "Download transcript JSON",
                data=json_text(transcript),
                file_name=st.session_state.transcript_path.name,
                mime="application/json",
                use_container_width=True,
            )
            st.markdown("**Requirements coverage**")
            st.write("- Request / final response")
            st.write("- Tool trace per round")
            st.write("- Transcript + artifact version")
            st.write("- Reusable for demo across versions")

    with tab_runs:
        render_run_explorer()

    with tab_compare:
        render_version_compare()

    with tab_transcripts:
        render_transcript_browser()


if __name__ == "__main__":
    main()
