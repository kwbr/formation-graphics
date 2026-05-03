from __future__ import annotations

from pathlib import Path
from typing import Any

from .config_model import MatchConfig
from .planning import (
    ALL_POSITIONS,
    DEFAULT_EXAMPLE_CONFIG_PATH,
    DEFAULT_LOCAL_CONFIG_PATH,
    GROUP,
    MIRROR,
    OUTFIELD_POSITIONS,
    SegmentPlan,
    assign_positions_for_segment,
    build_non_goalie_targets,
    build_schedule,
    choose_combo_for_slot,
    choose_global_block_count,
    ensure_match_config,
    load_game_config,
    plan_match,
    preference_penalty,
    validate_config,
)
from .publishing import (
    compute_player_stats,
    compute_transition_markers,
    draw_segment_image,
    draw_segment_on_axis,
    open_images_in_order,
    pitch_positions,
    publish_outputs,
    write_half_sheets_a4,
    write_player_stats_csv,
    write_schedule_csv,
    write_summary,
)


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
