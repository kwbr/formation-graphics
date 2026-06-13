from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

OUTFIELD_POSITIONS = ("LB", "RB", "LM", "CM", "RM", "ST")


@dataclass(frozen=True)
class PlayerConfig:
    positions: tuple[str, ...]


@dataclass(frozen=True)
class MatchConfig:
    game_id: str
    game_minutes: int
    players: dict[str, PlayerConfig]
    gk1: str
    gk2: str
    kickoff_starters: tuple[str, ...]


def parse_match_config(data: dict[str, Any]) -> MatchConfig:
    errors: list[str] = []

    players_raw = data.get("players", {})
    players = list(players_raw.keys()) if isinstance(players_raw, dict) else []
    unique_players = set(players)

    game_minutes = data.get("game_minutes")
    if not isinstance(game_minutes, int) or game_minutes <= 0:
        errors.append("game_minutes must be a positive integer")

    if len(players) != len(unique_players):
        errors.append("players contains duplicate names")

    if not (7 <= len(players) <= 11):
        errors.append(f"player count must be 7..11, got {len(players)}")

    gk1 = data.get("gk1")
    gk2 = data.get("gk2")
    if gk1 not in unique_players:
        errors.append(f"gk1 '{gk1}' is not in players")
    if gk2 not in unique_players:
        errors.append(f"gk2 '{gk2}' is not in players")
    if gk1 == gk2:
        errors.append("gk1 and gk2 must be different players")

    starters = data.get("kickoff_starters", [])
    if not isinstance(starters, list):
        errors.append("kickoff_starters must be a list")
    else:
        if len(starters) != 7:
            errors.append(f"kickoff_starters must have exactly 7 names, got {len(starters)}")
        if len(starters) != len(set(starters)):
            errors.append("kickoff_starters contains duplicates")
        unknown = [s for s in starters if s not in unique_players]
        if unknown:
            errors.append(f"kickoff_starters has unknown players: {unknown}")
        if gk1 not in starters:
            errors.append("kickoff_starters must include gk1")
        if gk2 not in starters:
            errors.append("kickoff_starters must include gk2")

    typed_players: dict[str, PlayerConfig] = {}
    if isinstance(players_raw, dict):
        for name, info in players_raw.items():
            prefs = info.get("positions") if isinstance(info, dict) else None
            if not isinstance(prefs, list) or not prefs:
                errors.append(f"{name}: positions must be a non-empty list")
                continue
            invalid = [p for p in prefs if p not in OUTFIELD_POSITIONS]
            if invalid:
                errors.append(f"{name}: invalid preferred positions: {invalid}")
                continue
            if len(prefs) != len(set(prefs)):
                errors.append(f"{name}: positions contains duplicates")
                continue
            typed_players[name] = PlayerConfig(positions=tuple(prefs))

    game_id = data.get("game_id")
    if not isinstance(game_id, str) or not game_id.strip():
        errors.append("game_id must be a non-empty string")

    if errors:
        raise ValueError("Invalid GAME_CONFIG:\n- " + "\n- ".join(errors))

    return MatchConfig(
        game_id=game_id,
        game_minutes=game_minutes,
        players=typed_players,
        gk1=gk1,
        gk2=gk2,
        kickoff_starters=tuple(starters),
    )


def load_match_config(config_path: Path, example_path: Path) -> MatchConfig:
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Create it from {example_path} and keep it untracked."
        )

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in config file: {config_path} ({exc})") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Config root must be a JSON object: {config_path}")

    return parse_match_config(data)
