from __future__ import annotations

from pathlib import Path
from typing import Any

from .backends import BackendTurnResult


ReplayCapture = dict[str, list[str]]


def new_replay_capture() -> ReplayCapture:
    """Return a mutable holder for the latest full battle/replay logs.

    Showdown bridge calls currently return cumulative battle protocol lines after
    replaying the full history. Keeping the latest non-empty list is enough to
    save the final battle log at the end of a game. Python backend logs are not
    Showdown-viewer compatible, but the same helper can still save them for
    debugging.
    """
    return {"log_lines": [], "input_log": []}


def update_replay_capture(capture: ReplayCapture | None, result: BackendTurnResult) -> None:
    """Update a replay capture from a backend turn/replacement result."""
    if capture is None:
        return
    if result.log_lines:
        capture["log_lines"] = list(result.log_lines)
    input_log = result.raw.get("input_log") if isinstance(result.raw, dict) else None
    if isinstance(input_log, list) and all(isinstance(line, str) for line in input_log):
        capture["input_log"] = list(input_log)


def write_replay_files(
    directory: str | Path,
    *,
    game_id: int,
    metadata: dict[str, Any],
    log_lines: list[str] | None = None,
    input_log: list[str] | None = None,
) -> dict[str, str | int | None]:
    """Write raw battle log files plus metadata for one game.

    The ``.log`` file is the raw backend battle log. For ShowdownBackend this is
    the Showdown battle protocol log returned by the local simulator. It is not
    a hosted replay link; it is a local artifact that can later be fed into a
    replay-viewer/export tool.
    """
    out_dir = Path(directory)
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = f"game_{game_id:04d}"
    log_path = out_dir / f"{stem}.log"
    meta_path = out_dir / f"{stem}.json"
    input_path = out_dir / f"{stem}.input.log"

    final_log_lines = list(log_lines or [])
    final_input_log = list(input_log or [])

    log_path.write_text("\n".join(final_log_lines) + ("\n" if final_log_lines else ""), encoding="utf-8")

    input_log_path: Path | None = None
    if final_input_log:
        input_path.write_text("\n".join(final_input_log) + "\n", encoding="utf-8")
        input_log_path = input_path

    meta_payload: dict[str, Any] = {
        **metadata,
        "artifact_type": "raw_backend_battle_log",
        "replay_log_path": str(log_path),
        "input_log_path": str(input_log_path) if input_log_path is not None else None,
        "line_count": len(final_log_lines),
        "input_line_count": len(final_input_log),
        "viewer_note": (
            "Showdown backend .log files contain raw Showdown battle protocol lines, "
            "not hosted pokemonshowdown.com replay URLs."
        ),
    }
    meta_path.write_text(__import__("json").dumps(meta_payload, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "replay_log_path": str(log_path),
        "metadata_path": str(meta_path),
        "input_log_path": str(input_log_path) if input_log_path is not None else None,
        "line_count": len(final_log_lines),
        "input_line_count": len(final_input_log),
    }
