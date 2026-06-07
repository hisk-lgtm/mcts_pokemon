from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def _active_line(label: str, side: dict) -> str:
    active = side.get("active", "?")
    hp = side.get("hp", "?")
    max_hp = side.get("max_hp", "?")
    status = side.get("status") or "healthy"
    alive = side.get("alive", "?")
    hazards = side.get("hazards", {})
    hazard_bits = []
    if hazards.get("sr"):
        hazard_bits.append("SR")
    if hazards.get("spikes"):
        hazard_bits.append(f"Spikes x{hazards['spikes']}")
    if hazards.get("toxic_spikes"):
        hazard_bits.append(f"TSpikes x{hazards['toxic_spikes']}")
    hazard_text = ", ".join(hazard_bits) if hazard_bits else "no hazards"
    return f"{label}: {active} {hp}/{max_hp} [{status}] | alive {alive}/6 | {hazard_text}"


def _format_mcts_block(label: str, mcts: dict, *, top_n: int = 5) -> list[str]:
    lines = []
    stats = mcts.get("stats", [])[:top_n]
    if not stats:
        return [f"{label} MCTS: no stats"]

    lines.append(f"{label} MCTS top {min(top_n, len(stats))}:")
    for stat in stats:
        action_label = stat.get("label", "?")
        visits = stat.get("visits", 0)
        value = stat.get("mean_value", 0.0)
        prior = stat.get("prior", 0.0)
        lines.append(f"  - {action_label:<28} visits={visits:<3} value={value:>7} prior={prior:>6}")
    return lines


def format_training_event(event: dict, *, top_n: int = 5) -> str:
    event_type = event.get("type")


    if event_type == "team_preview":
        def team_lines(label: str, summary: dict, score: float) -> list[str]:
            role_counts = summary.get("role_counts", {})
            members = summary.get("members", [])
            lines = [f"{label} team score: {score:.3f}"]
            lines.append(f"{label} roles: " + ", ".join(f"{k}={v}" for k, v in sorted(role_counts.items()) if v))
            lines.append(f"{label} members:")
            for member in members:
                core_tags = [t for t in member.get("tags", []) if not t.startswith("coverage:") and not t.startswith("type:")]
                lines.append(
                    f"  - {member.get('species')} @ {member.get('item')} | "
                    f"{member.get('ability')} | tags: {', '.join(core_tags[:10])}"
                )
            return lines

        lines = [
            f"=== {event.get('game_id', '?')} | Team Preview ===",
            f"P1 agent {event.get('p1_agent_id')}: {event.get('p1_agent_name', '?')}",
            f"P2 agent {event.get('p2_agent_id')}: {event.get('p2_agent_name', '?')}",
            f"Candidate teams scored per agent: {event.get('candidate_count', '?')}",
            "",
            f"P1: {event.get('p1_team_label', '?')}",
        ]
        lines.extend(team_lines("P1", event.get("p1_team", {}), event.get("p1_team_score", 0.0)))
        lines.append("")
        lines.append(f"P2: {event.get('p2_team_label', '?')}")
        lines.extend(team_lines("P2", event.get("p2_team", {}), event.get("p2_team_score", 0.0)))
        return "\n".join(lines)

    if event_type == "turn":
        state = event.get("state", {})
        turn = state.get("turn", event.get("turn_index", "?"))
        weather = state.get("weather") or "none"
        trick_room = state.get("trick_room_turns", 0)
        lines = [
            f"=== {event.get('game_id', '?')} | Turn {turn} ===",
            f"Field: weather={weather}, trick_room_turns={trick_room}",
            _active_line("P1", state.get("p1", {})),
            _active_line("P2", state.get("p2", {})),
            "",
            f"P1 chose: {event.get('p1_action', '?')}",
            f"P2 chose: {event.get('p2_action', '?')}",
            "",
        ]
        lines.extend(_format_mcts_block("P1", event.get("p1_mcts", {}), top_n=top_n))
        lines.append("")
        lines.extend(_format_mcts_block("P2", event.get("p2_mcts", {}), top_n=top_n))
        lines.append("")
        lines.append("Battle log:")
        for line in event.get("turn_log", []):
            lines.append(f"  {line}")
        return "\n".join(lines)

    if event_type == "game_result":
        winner = event.get("winner")
        winner_text = "draw/unfinished" if winner in (None, 0) else f"Player {winner}"
        final = event.get("final", {})
        return "\n".join([
            f"=== {event.get('game_id', '?')} | Result ===",
            f"Winner: {winner_text}",
            f"Turns: {event.get('turns', '?')}",
            f"P1 value: {event.get('p1_value', '?')}",
            f"P2 value: {event.get('p2_value', '?')}",
            _active_line("Final P1", final.get("p1", {})),
            _active_line("Final P2", final.get("p2", {})),
        ])


    if event_type == "swiss_pairings":
        lines = [f"=== Generation {event.get('generation', '?')} | Swiss Round {event.get('swiss_round', '?')} Pairings ==="]
        for pair in event.get("pairings", []):
            p1_elo = pair.get("p1_elo")
            p2_elo = pair.get("p2_elo")
            elo_text = f" ({p1_elo} vs {p2_elo})" if p1_elo is not None and p2_elo is not None else ""
            lines.append(f"Agent {pair.get('p1_agent_id')} vs Agent {pair.get('p2_agent_id')}{elo_text}")
        if event.get("bye_agent_id") is not None:
            bye_elo = event.get("bye_elo")
            elo_text = f" ({bye_elo})" if bye_elo is not None else ""
            lines.append(f"Bye: Agent {event.get('bye_agent_id')}{elo_text}")
        return "\n".join(lines)


    if event_type == "elo_update":
        return "\n".join([
            f"=== {event.get('game_id', '?')} | Elo Update ===",
            f"Winner: {event.get('winner')}",
            (
                f"Agent {event.get('p1_agent_id')}: "
                f"{event.get('p1_old_elo')} -> {event.get('p1_new_elo')} "
                f"({event.get('p1_elo_delta'):+}) | expected={event.get('p1_expected')}"
            ),
            (
                f"Agent {event.get('p2_agent_id')}: "
                f"{event.get('p2_old_elo')} -> {event.get('p2_new_elo')} "
                f"({event.get('p2_elo_delta'):+}) | expected={event.get('p2_expected')}"
            ),
            f"K-factor: {event.get('k_factor')}",
        ])

    if event_type == "swiss_standings":
        round_text = "final" if event.get("swiss_round") is None else f"after round {event.get('swiss_round')}"
        lines = [f"=== Generation {event.get('generation', '?')} Standings ({round_text}) ==="]
        for rank, row in enumerate(event.get("standings", []), start=1):
            lines.append(
                f"{rank:>2}. Agent {row.get('agent_id')} {row.get('name', '')} | "
                f"{row.get('points')} pts | Elo {row.get('elo', '?')} ({row.get('elo_delta', 0):+}) | "
                f"W-L-D {row.get('wins')}-{row.get('losses')}-{row.get('draws')} | "
                f"byes={row.get('byes')} | avg_turns={row.get('avg_turns', 0):.1f}"
            )
        return "\n".join(lines)

    if event_type == "generation_summary":
        lines = [
            f"=== Generation {event.get('generation', '?')} Summary ===",
            f"Agents: {event.get('agents', '?')}",
            f"Swiss rounds: {event.get('swiss_rounds', '?')}",
            f"Games: {event.get('games', '?')}",
            f"Best agent: {event.get('best_agent_id', '?')} with {event.get('best_points', '?')} pts",
            f"Best Elo: {event.get('best_elo', '?')}",
            f"Average Elo: {event.get('avg_elo', '?')}",
        ]
        standings = event.get("standings", [])
        if standings:
            lines.append("Final standings:")
            for rank, row in enumerate(standings, start=1):
                lines.append(
                    f"  {rank:>2}. Agent {row.get('agent_id')} {row.get('name', '')} | "
                    f"{row.get('points')} pts | Elo {row.get('elo', '?')} ({row.get('elo_delta', 0):+}) | "
                    f"W-L-D {row.get('wins')}-{row.get('losses')}-{row.get('draws')}"
                )
        return "\n".join(lines)

    return "=== Unknown event ===\n" + json.dumps(event, indent=2, sort_keys=True)


def iter_training_events(path: str | Path) -> Iterable[dict]:
    with Path(path).open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Could not parse JSONL line {line_number} in {path}: {exc}") from exc


def format_training_log_file(
    input_path: str | Path,
    *,
    output_path: str | Path | None = None,
    top_n: int = 5,
) -> str:
    chunks = [format_training_event(event, top_n=top_n) for event in iter_training_events(input_path)]
    text = "\n\n".join(chunks)
    if text:
        text += "\n"
    if output_path is not None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(text, encoding="utf-8")
    return text


def append_human_event(log_file, event: dict, *, top_n: int = 5) -> None:
    log_file.write(format_training_event(event, top_n=top_n))
    log_file.write("\n\n")
    log_file.flush()
