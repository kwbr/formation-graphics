from __future__ import annotations

from pathlib import Path
from typing import Any

from .config_model import MatchConfig
from .planning import ensure_match_config, plan_match
from .publishing import publish_outputs


def generate(cfg: MatchConfig | dict[str, Any]) -> Path:
    match = ensure_match_config(cfg)
    game_id = match.game_id
    out_dir = Path("output") / game_id
    out_dir.mkdir(parents=True, exist_ok=True)

    plan = plan_match(match, strategy="heuristic")
    publish_outputs(
        segments=plan.segments,
        cfg=match,
        global_block_count=plan.global_block_count,
        out_dir=out_dir,
        game_id=game_id,
    )

    return out_dir
