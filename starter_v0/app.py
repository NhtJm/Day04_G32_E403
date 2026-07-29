from __future__ import annotations

import csv
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st
import yaml

from chat import ROOT, now_iso, run_model_tool_loop, safe_slug, trim_history, write_transcript
from env_loader import load_lab_env
from providers import make_provider
from tools import to_openai_tools
from versioning import artifact_version_dict, build_artifact_version


ARTIFACTS_DIR = ROOT / "artifacts"
RUNS_DIR = ROOT / "runs"
TRANSCRIPTS_DIR = ROOT / "transcripts"
SYSTEM_PROMPT_PATH = ARTIFACTS_DIR / "system_prompt.md"
TOOLS_PATH = ARTIFACTS_DIR / "tools.yaml"
VERSION_LOG_PATH = ARTIFACTS_DIR / "version_log.csv"
REPO_ROOT = ROOT.parent
V3_VIETNAMESE_LINE = "Return Vietnamese output if you can"

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


def read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def run_files() -> list[Path]:
    return sorted(RUNS_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)


def transcript_files() -> list[Path]:
    return sorted(TRANSCRIPTS_DIR.glob("*.transcript.json"), key=lambda item: item.stat().st_mtime, reverse=True)


def version_log_rows() -> list[dict[str, str]]:
    if not VERSION_LOG_PATH.exists():
        return []
    try:
        with VERSION_LOG_PATH.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except Exception:
        return []


def available_versions() -> list[str]:
    allowed = ["v0", "v1", "v2", "v3"]
    present = {row.get("version", "").strip() for row in version_log_rows()}
    versions = [version for version in allowed if version in present]
    return versions or ["v3"]


def version_run_options(version: str) -> dict[str, Path]:
    options: dict[str, Path] = {}
    for row in version_log_rows():
        if row.get("version") != version:
            continue
        run_file_field = (row.get("run_file") or "").strip()
        if not run_file_field:
            continue
        for raw_path in [item.strip() for item in run_file_field.split(";") if item.strip()]:
            run_path = ROOT / raw_path
            if not run_path.exists():
                continue
            label = "group" if "_group_" in run_path.name.lower() else "base"
            options[label] = run_path
    return options


def latest_transcript_for_version(version: str) -> dict[str, Any] | None:
    for path in transcript_files():
        payload = read_json_file(path)
        if payload and payload.get("version") == version:
            return payload
    return None


def latest_turn_from_transcript(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not payload:
        return None
    turns = payload.get("turns", [])
    if not turns:
        return None
    return turns[-1]


@st.cache_data(show_spinner=False)
def git_show_text(commit: str, repo_relative_path: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", f"{commit}:{repo_relative_path}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout


def current_prompt_without_v3_line() -> str:
    prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    lines = prompt.splitlines()
    if lines and lines[-1].strip() == V3_VIETNAMESE_LINE:
        lines = lines[:-1]
    return "\n".join(lines).rstrip() + "\n"


def artifact_texts_for_version(version: str) -> tuple[str, str]:
    if version == "v0":
        return (
            git_show_text("ff7427d", "starter_v0/artifacts/system_prompt.md"),
            git_show_text("ff7427d", "starter_v0/artifacts/tools.yaml"),
        )
    if version == "v1":
        return (
            git_show_text("dc9bb22", "starter_v0/artifacts/system_prompt.md"),
            git_show_text("ff7427d", "starter_v0/artifacts/tools.yaml"),
        )
    if version == "v2":
        return (
            current_prompt_without_v3_line(),
            git_show_text("dc9bb22", "starter_v0/artifacts/tools.yaml"),
        )
    return (
        SYSTEM_PROMPT_PATH.read_text(encoding="utf-8"),
        TOOLS_PATH.read_text(encoding="utf-8"),
    )


def tool_declarations_from_text(tools_text: str) -> list[dict[str, Any]]:
    return yaml.safe_load(tools_text)["tools"]


def write_version_snapshot(version: str) -> tuple[Path, Path]:
    prompt_text, tools_text = artifact_texts_for_version(version)
    snapshot_dir = ARTIFACTS_DIR / "ui_snapshots" / version
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = snapshot_dir / "system_prompt.md"
    tools_path = snapshot_dir / "tools.yaml"
    prompt_path.write_text(prompt_text, encoding="utf-8")
    tools_path.write_text(tools_text, encoding="utf-8")
    return prompt_path, tools_path


def build_transcript(
    version: str,
    provider_name: str,
    model: str | None,
    history_window: int,
    max_tool_rounds: int,
) -> tuple[dict[str, Any], Path]:
    prompt_path, tools_path = write_version_snapshot(version)
    artifact_version = build_artifact_version(version, prompt_path, tools_path)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    transcript_id = "_".join([safe_slug(version), safe_slug(provider_name), timestamp])
    transcript_path = TRANSCRIPTS_DIR / f"{transcript_id}.transcript.json"
    transcript = {
        "transcript_id": transcript_id,
        **artifact_version_dict(artifact_version),
        "provider": provider_name,
        "model": model,
        "system_prompt": str(prompt_path),
        "tools": str(tools_path),
        "history_window": history_window,
        "max_tool_rounds": max_tool_rounds,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "turns": [],
    }
    return transcript, transcript_path


def reset_session(
    version: str,
    provider_name: str,
    model: str | None,
    history_window: int,
    max_tool_rounds: int,
) -> None:
    transcript, transcript_path = build_transcript(version, provider_name, model, history_window, max_tool_rounds)
    st.session_state.chat_history = []
    st.session_state.turns = []
    st.session_state.transcript = transcript
    st.session_state.transcript_path = transcript_path
    st.session_state.last_error = None
    write_transcript(transcript_path, transcript)


def ensure_transcript(
    version: str,
    provider_name: str,
    model: str | None,
    history_window: int,
    max_tool_rounds: int,
) -> None:
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


def execute_versioned_request(
    *,
    version: str,
    provider_name: str,
    model: str | None,
    history_messages: list[dict[str, str]],
    user_text: str,
    max_tool_rounds: int,
) -> dict[str, Any]:
    prompt_text, tools_text = artifact_texts_for_version(version)
    tool_declarations = tool_declarations_from_text(tools_text)
    openai_tools = to_openai_tools(tool_declarations)
    provider = make_provider(provider_name)
    messages = [
        {"role": "system", "content": prompt_text},
        *history_messages,
        {"role": "user", "content": user_text},
    ]
    result = run_model_tool_loop(
        provider=provider,
        messages=messages,
        tools=openai_tools,
        model=model,
        max_tool_rounds=max_tool_rounds,
    )
    prompt_path, tools_path = write_version_snapshot(version)
    artifact_version = build_artifact_version(version, prompt_path, tools_path)
    return {
        "version": version,
        "artifact_version": artifact_version.artifact_version,
        "prompt_hash": artifact_version.prompt_hash,
        "tools_hash": artifact_version.tools_hash,
        **result,
    }


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
    history_messages = trim_history(st.session_state.chat_history, history_window)

    turn_index = len(st.session_state.turns) + 1
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
        result = execute_versioned_request(
            version=version,
            provider_name=provider_name,
            model=model,
            history_messages=history_messages,
            user_text=user_text,
            max_tool_rounds=max_tool_rounds,
        )
        turn_record.update({
            "status": result["status"],
            "assistant_text": result["assistant_text"],
            "rounds": result["rounds"],
            "tool_events": result["tool_events"],
        })
        st.session_state.chat_history.append({"role": "user", "content": user_text})
        st.session_state.chat_history.append({"role": "assistant", "content": result["assistant_text"]})
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

    st.markdown("**Input**")
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


def render_version_summary(label: str, version: str, dataset: str) -> None:
    st.markdown(f"**{label}: {version}**")
    run_path = version_run_options(version).get(dataset)
    if not run_path:
        st.info(f"Không có run `{dataset}` cho `{version}`.")
        return
    payload = read_json_file(run_path)
    if not payload:
        st.error(f"Không đọc được `{run_path.name}`.")
        return
    summary = payload.get("summary", {})
    st.caption(f"`{run_path.name}`")
    st.write(f"Artifact: `{payload.get('artifact_version')}`")
    st.write(f"Case accuracy: `{summary.get('case_accuracy')}`")
    st.write(f"Passed: `{summary.get('passed_cases')}/{summary.get('total_cases')}`")


def render_version_compare(provider_name: str, model: str | None, max_tool_rounds: int) -> None:
    st.subheader("Version Compare")
    versions = available_versions()
    if len(versions) < 2:
        st.info("Cần ít nhất 2 version trong `version_log.csv` để so sánh.")
        return

    dataset = st.selectbox("Dataset", ["base", "group"], key="compare_dataset")
    left_col, right_col = st.columns(2)
    left_version = left_col.selectbox("Version A", versions, key="compare_left_version")
    right_version = right_col.selectbox("Version B", versions, index=1 if len(versions) > 1 else 0, key="compare_right_version")

    left_file = version_run_options(left_version).get(dataset)
    right_file = version_run_options(right_version).get(dataset)

    summary_col_a, summary_col_b = st.columns(2)
    with summary_col_a:
        render_version_summary("Version A", left_version, dataset)
    with summary_col_b:
        render_version_summary("Version B", right_version, dataset)

    if left_file and right_file:
        left_payload = read_json_file(left_file)
        right_payload = read_json_file(right_file)
        if left_payload and right_payload:
            common_case_ids = sorted(
                set(item.get("id") for item in left_payload.get("results", []))
                & set(item.get("id") for item in right_payload.get("results", []))
            )
            if common_case_ids:
                selected_case_id = st.selectbox("Scenario / Case ID", common_case_ids, key="compare_case")
                left_case = next(item for item in left_payload["results"] if item.get("id") == selected_case_id)
                right_case = next(item for item in right_payload["results"] if item.get("id") == selected_case_id)

                st.caption(f"Comparing `{selected_case_id}` across artifact versions.")
                col_a, col_b = st.columns(2)
                for col, label, payload, case in [
                    (col_a, "Version A", left_payload, left_case),
                    (col_b, "Version B", right_payload, right_case),
                ]:
                    with col:
                        st.markdown(f"**{label}: {payload.get('artifact_version')}**")
                        st.write(f"Passed: `{case.get('result', {}).get('passed')}`")
                        st.code(json_text(case.get("result", {}).get("actual_tool_calls", [])), language="json")
                        st.code(json_text(case.get("result", {}).get("failures", [])), language="json")

    st.markdown("---")
    st.markdown("**Scenario Replay Qua Nhiều Version**")
    st.caption("Chạy cùng một request qua nhiều prompt/tool version để thấy khác biệt thật.")
    replay_versions = st.multiselect(
        "Chọn version để replay",
        versions,
        default=versions,
        key="replay_versions",
    )
    replay_request = st.text_area(
        "Request demo",
        value="Gửi bản tin AI hôm nay lên Telegram giúp mình.",
        key="replay_request",
        height=100,
    )
    if st.button("Run Replay", key="run_replay", use_container_width=True):
        if not replay_versions or not replay_request.strip():
            st.warning("Hãy chọn ít nhất một version và nhập request demo.")
        else:
            for version in replay_versions:
                with st.container(border=True):
                    st.markdown(f"**{version}**")
                    try:
                        replay_result = execute_versioned_request(
                            version=version,
                            provider_name=provider_name,
                            model=model,
                            history_messages=[],
                            user_text=replay_request.strip(),
                            max_tool_rounds=max_tool_rounds,
                        )
                        st.caption(
                            f"artifact_version={replay_result['artifact_version']} • "
                            f"prompt_hash={replay_result['prompt_hash'][:12]} • tools_hash={replay_result['tools_hash'][:12]}"
                        )
                        st.write("Assistant response")
                        st.code(replay_result.get("assistant_text", ""))
                        st.write("Tool calls")
                        tool_calls: list[dict[str, Any]] = []
                        for round_record in replay_result.get("rounds", []):
                            tool_calls.extend(round_record.get("tool_calls", []))
                        st.code(json_text(tool_calls), language="json")
                    except Exception as exc:
                        st.error(f"{type(exc).__name__}: {exc}")

    st.markdown("---")
    st.markdown("**Compare Theo Request Mới Nhất**")
    st.caption("Lấy turn mới nhất trong transcript của mỗi version để đối chiếu request, response và tool calls.")
    latest_col_a, latest_col_b = st.columns(2)
    for col, label, version in [
        (latest_col_a, "Version A", left_version),
        (latest_col_b, "Version B", right_version),
    ]:
        with col:
            st.markdown(f"**{label}: {version}**")
            transcript = latest_transcript_for_version(version)
            turn = latest_turn_from_transcript(transcript)
            if not transcript or not turn:
                st.info("Chưa có transcript cho version này.")
                continue
            st.caption(f"`{transcript.get('transcript_id')}`")
            st.write("Latest request")
            st.code(str(turn.get("user", "")))
            st.write("Assistant response")
            st.code(str(turn.get("assistant_text", "")))
            tool_calls: list[dict[str, Any]] = []
            for round_record in turn.get("rounds", []):
                tool_calls.extend(round_record.get("tool_calls", []))
            st.write("Tool calls")
            st.code(json_text(tool_calls), language="json")


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
        versions = available_versions()
        default_version = "v3" if "v3" in versions else versions[-1]
        version = st.selectbox("Version", versions, index=versions.index(default_version))
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
            st.write("- Live chat chạy theo đúng version đã chọn")

    with tab_runs:
        render_run_explorer()

    with tab_compare:
        render_version_compare(provider_name, model or None, int(max_tool_rounds))

    with tab_transcripts:
        render_transcript_browser()


if __name__ == "__main__":
    main()
