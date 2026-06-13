from __future__ import annotations

import csv
import math
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

from .config_model import MatchConfig, PlayerConfig
from .planning import ALL_POSITIONS, MIRROR, SegmentPlan, ensure_match_config


def pitch_positions() -> Dict[str, Tuple[float, float]]:
    return {
        "GK": (0.50, 0.08),
        "LB": (0.30, 0.30),
        "RB": (0.70, 0.30),
        "LM": (0.20, 0.55),
        "CM": (0.50, 0.55),
        "RM": (0.80, 0.55),
        "ST": (0.50, 0.82),
    }


def compute_half_offsets(segments: List[SegmentPlan]) -> Dict[int, float]:
    offsets: Dict[int, float] = {}
    for segment in segments:
        offsets[segment.half] = min(segment.start_min, offsets.get(segment.half, segment.start_min))
    return offsets


def draw_segment_on_axis(
    ax,
    segment: SegmentPlan,
    all_players: List[str],
    incoming_players: set[str] | None = None,
    moved_players: set[str] | None = None,
    compact: bool = False,
    half_offset: float | None = None,
) -> None:
    coords = pitch_positions()
    ax.add_patch(Rectangle((0, 0), 1, 1, facecolor="#f4f4f4", edgecolor="black", linewidth=2))
    ax.plot([0, 1], [0.5, 0.5], color="black", linewidth=1.2)
    ax.add_patch(Circle((0.5, 0.5), 0.08, fill=False, edgecolor="black", linewidth=1.0))
    ax.add_patch(Rectangle((0.2, 0), 0.6, 0.12, fill=False, edgecolor="black", linewidth=1.0))

    incoming_players = incoming_players or set()
    moved_players = moved_players or set()

    marker_r = 0.045 if not compact else 0.04
    font_size = 9 if not compact else 7

    for pos in ALL_POSITIONS:
        player = segment.lineup[pos]
        x, y = coords[pos]

        ax.add_patch(Circle((x, y), marker_r, facecolor="white", edgecolor="black", linewidth=1.2))

        if player in incoming_players:
            ax.add_patch(
                Circle((x, y), marker_r + 0.013, fill=False, edgecolor="black", linewidth=2.2)
            )
        if player in moved_players:
            ax.add_patch(
                Circle(
                    (x, y),
                    marker_r + 0.021,
                    fill=False,
                    edgecolor="black",
                    linewidth=1.8,
                    linestyle=(0, (3, 2)),
                )
            )

        ax.text(
            x,
            y,
            f"{pos}\n{player}",
            ha="center",
            va="center",
            color="black",
            fontsize=font_size,
            weight="bold",
        )

    on_field = set(segment.lineup.values())
    bench = sorted([p for p in all_players if p not in on_field])
    if half_offset is None:
        half_offset = 0.0 if segment.half == 1 else 20.0

    if compact:
        compact_title = (
            f"H{segment.half} S{segment.half_segment_index} "
            f"({segment.start_min - half_offset:.1f}-{segment.end_min - half_offset:.1f})"
        )
        ax.set_title(compact_title, fontsize=10, weight="bold")
        ax.text(
            0.01,
            -0.08,
            f"Bench: {', '.join(bench) if bench else 'None'}",
            transform=ax.transAxes,
            fontsize=8,
            color="black",
        )
    else:
        ax.text(
            0.01,
            -0.08,
            f"Bench: {', '.join(bench) if bench else 'None'}",
            transform=ax.transAxes,
            fontsize=10,
            color="black",
        )
        incoming_label = ", ".join(sorted(incoming_players)) if incoming_players else "None"
        ax.text(
            0.01,
            -0.13,
            f"Coming on (solid ring): {incoming_label}",
            transform=ax.transAxes,
            fontsize=10,
            color="black",
        )
        moved_label = ", ".join(sorted(moved_players)) if moved_players else "None"
        ax.text(
            0.01,
            -0.18,
            f"Position change (dashed ring): {moved_label}",
            transform=ax.transAxes,
            fontsize=10,
            color="black",
        )
        abs_range = f"{segment.start_min:.1f}-{segment.end_min:.1f}"
        half_range = f"{segment.start_min - half_offset:.1f}-{segment.end_min - half_offset:.1f}"
        title = (
            f"Half {segment.half} Segment {segment.half_segment_index} "
            f"(global {segment.global_block}, abs {abs_range} min, half {half_range})"
        )
        ax.set_title(title, fontsize=14, weight="bold")

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.axis("off")


def draw_segment_image(
    segment: SegmentPlan,
    all_players: List[str],
    players_cfg: dict[str, PlayerConfig],
    out_path: Path,
    incoming_players: set[str] | None = None,
    moved_players: set[str] | None = None,
    half_offset: float | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=(10, 6))
    draw_segment_on_axis(
        ax,
        segment,
        all_players,
        incoming_players=incoming_players,
        moved_players=moved_players,
        compact=False,
        half_offset=half_offset,
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def compute_transition_markers(segments: List[SegmentPlan]) -> List[Tuple[set[str], set[str]]]:
    markers: List[Tuple[set[str], set[str]]] = []
    prev_on_field: set[str] | None = None
    prev_player_pos: Dict[str, str] | None = None

    for s in segments:
        current_on_field = set(s.lineup.values())
        current_player_pos = {player: pos for pos, player in s.lineup.items()}

        incoming = set() if prev_on_field is None else (current_on_field - prev_on_field)
        moved = set()
        if prev_player_pos is not None:
            for player in current_on_field & (prev_on_field or set()):
                if current_player_pos[player] != prev_player_pos.get(player):
                    moved.add(player)

        markers.append((incoming, moved))
        prev_on_field = current_on_field
        prev_player_pos = current_player_pos

    return markers


def write_half_sheets_a4(
    segments: List[SegmentPlan], all_players: List[str], out_dir: Path, game_id: str
) -> None:
    markers = compute_transition_markers(segments)
    half_offsets = compute_half_offsets(segments)

    for half in (1, 2):
        idxs = [i for i, s in enumerate(segments) if s.half == half]
        if not idxs:
            continue

        n = len(idxs)
        if n <= 2:
            cols = 1
        elif n <= 4:
            cols = 2
        else:
            cols = 3
        rows = math.ceil(n / cols)

        fig, axes = plt.subplots(rows, cols, figsize=(8.27, 11.69))
        if hasattr(axes, "flatten"):
            axes_list = list(axes.flatten())
        elif isinstance(axes, list):
            axes_list = axes
        else:
            axes_list = [axes]

        for ax in axes_list:
            ax.axis("off")

        for slot, idx in enumerate(idxs):
            s = segments[idx]
            incoming, moved = markers[idx]
            draw_segment_on_axis(
                axes_list[slot],
                s,
                all_players,
                incoming_players=incoming,
                moved_players=moved,
                compact=True,
                half_offset=half_offsets[s.half],
            )

        suptitle = (
            f"{game_id} - Half {half} Rotation Sheet (A4)\n"
            "Solid ring=coming on, dashed ring=position change"
        )
        fig.suptitle(suptitle, fontsize=12, weight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.96))
        fig.savefig(out_dir / f"half{half}_sheet_a4.pdf")
        fig.savefig(out_dir / f"half{half}_sheet_a4.png", dpi=300)
        plt.close(fig)


def write_schedule_csv(segments: List[SegmentPlan], all_players: List[str], path: Path) -> None:
    half_offsets = compute_half_offsets(segments)
    fields = [
        "half",
        "half_segment_index",
        "global_block",
        "start_min",
        "end_min",
        "half_start_min",
        "half_end_min",
        *ALL_POSITIONS,
        "bench",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for s in segments:
            on_field = set(s.lineup.values())
            bench = sorted([p for p in all_players if p not in on_field])
            half_offset = half_offsets[s.half]
            row = {
                "half": s.half,
                "half_segment_index": s.half_segment_index,
                "global_block": s.global_block,
                "start_min": f"{s.start_min:.2f}",
                "end_min": f"{s.end_min:.2f}",
                "half_start_min": f"{s.start_min - half_offset:.2f}",
                "half_end_min": f"{s.end_min - half_offset:.2f}",
                "bench": ", ".join(bench),
            }
            for pos in ALL_POSITIONS:
                row[pos] = s.lineup[pos]
            writer.writerow(row)


def compute_player_stats(
    segments: List[SegmentPlan],
    all_players: List[str],
    players_cfg: dict[str, PlayerConfig],
) -> tuple[
    Dict[str, float],
    Dict[str, float],
    Dict[str, float],
    Dict[str, int],
    Dict[str, int],
    Dict[str, int],
]:
    total_minutes = {p: 0.0 for p in all_players}
    gk_minutes = {p: 0.0 for p in all_players}
    outfield_minutes = {p: 0.0 for p in all_players}
    pref_deviations = {p: 0 for p in all_players}
    segments_played = {p: 0 for p in all_players}
    segments_benched = {p: 0 for p in all_players}

    for s in segments:
        duration = s.end_min - s.start_min
        on_field = set(s.lineup.values())
        for p in all_players:
            if p in on_field:
                segments_played[p] += 1
            else:
                segments_benched[p] += 1

        for pos, p in s.lineup.items():
            total_minutes[p] += duration
            if pos == "GK":
                gk_minutes[p] += duration
            else:
                outfield_minutes[p] += duration
                prefs = players_cfg[p].positions
                if pos not in prefs and MIRROR.get(pos) not in prefs:
                    pref_deviations[p] += 1

    return (
        total_minutes,
        gk_minutes,
        outfield_minutes,
        pref_deviations,
        segments_played,
        segments_benched,
    )


def write_player_stats_csv(
    segments: List[SegmentPlan],
    all_players: List[str],
    players_cfg: dict[str, PlayerConfig],
    out_path: Path,
) -> None:
    (
        total_minutes,
        gk_minutes,
        outfield_minutes,
        pref_deviations,
        segments_played,
        segments_benched,
    ) = compute_player_stats(segments, all_players, players_cfg)

    fields = [
        "player",
        "total_minutes",
        "gk_minutes",
        "outfield_minutes",
        "segments_played",
        "segments_benched",
        "pref_deviation_segments",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for p in all_players:
            writer.writerow(
                {
                    "player": p,
                    "total_minutes": f"{total_minutes[p]:.2f}",
                    "gk_minutes": f"{gk_minutes[p]:.2f}",
                    "outfield_minutes": f"{outfield_minutes[p]:.2f}",
                    "segments_played": segments_played[p],
                    "segments_benched": segments_benched[p],
                    "pref_deviation_segments": pref_deviations[p],
                }
            )


def write_summary(
    segments: List[SegmentPlan],
    all_players: List[str],
    players_cfg: dict[str, PlayerConfig],
    gk1: str,
    gk2: str,
    game_minutes: int,
    global_block_count: int,
    out_path: Path,
) -> None:
    (
        total_minutes,
        gk_minutes,
        outfield_minutes,
        pref_deviations,
        _segments_played,
        _segments_benched,
    ) = compute_player_stats(segments, all_players, players_cfg)

    non_goalies = [p for p in all_players if p not in {gk1, gk2}]
    non_goalie_outfield = [outfield_minutes[p] for p in non_goalies]
    fairness_gap = (
        max(non_goalie_outfield) - min(non_goalie_outfield) if non_goalie_outfield else 0.0
    )

    lines = []
    lines.append("Formation Scheduler Summary")
    lines.append("=" * 28)
    lines.append(f"Game minutes: {game_minutes}")
    lines.append(f"Global blocks: {global_block_count}")
    lines.append(f"Global block minutes: {game_minutes / global_block_count:.3f}")
    lines.append("Note: blocks are global and can cross halftime.")
    lines.append("")
    lines.append(f"Goalie half assignments: H1={gk1}, H2={gk2}")
    lines.append(f"Non-goalie outfield fairness gap (max-min): {fairness_gap:.3f} minutes")
    lines.append("")
    lines.append("Per-player minutes:")

    for p in all_players:
        lines.append(
            f"- {p}: total={total_minutes[p]:.2f}, GK={gk_minutes[p]:.2f}, "
            f"outfield={outfield_minutes[p]:.2f}, pref_deviation_segments={pref_deviations[p]}"
        )

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def open_images_in_order(out_dir: Path) -> None:
    opener = shutil.which("open")
    if opener is None:
        print("Cannot auto-open images: 'open' command not found on this system.")
        return

    images = sorted(out_dir.glob("h*_segment*.png"))
    if not images:
        images = sorted(out_dir.glob("h*_block*.png"))
    if not images:
        print("No segment images found to open.")
        return

    subprocess.run([opener, *[str(p) for p in images]], check=False)


def publish_outputs(
    segments: List[SegmentPlan],
    cfg: MatchConfig | dict,
    global_block_count: int,
    out_dir: Path,
    game_id: str,
) -> None:
    match = ensure_match_config(cfg)
    all_players = list(match.players.keys())

    max_h1 = max((s.half_segment_index for s in segments if s.half == 1), default=0)
    max_h2 = max((s.half_segment_index for s in segments if s.half == 2), default=0)
    pad = max(2, len(str(max(max_h1, max_h2, 1))))

    markers = compute_transition_markers(segments)
    half_offsets = compute_half_offsets(segments)
    for idx, s in enumerate(segments):
        file_name = f"h{s.half}_segment{s.half_segment_index:0{pad}d}.png"
        incoming, moved = markers[idx]
        draw_segment_image(
            s,
            all_players,
            match.players,
            out_dir / file_name,
            incoming_players=incoming,
            moved_players=moved,
            half_offset=half_offsets[s.half],
        )

    write_half_sheets_a4(segments, all_players, out_dir, game_id)
    write_schedule_csv(segments, all_players, out_dir / "schedule.csv")
    write_player_stats_csv(segments, all_players, match.players, out_dir / "player_stats.csv")
    write_summary(
        segments=segments,
        all_players=all_players,
        players_cfg=match.players,
        gk1=match.gk1,
        gk2=match.gk2,
        game_minutes=match.game_minutes,
        global_block_count=global_block_count,
        out_path=out_dir / "summary.txt",
    )
