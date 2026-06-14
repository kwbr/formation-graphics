# Formation Graphics (7v7)

Generate a **Match Plan** from a **Match Config**, then publish **Segment Graphics**, **Half Sheet (A4)** pages, **Schedule CSV**, and **Player Stats CSV** artifacts.

## Privacy-safe Match Config workflow

- Commit only the **Example Config**: `config/game_config.example.json`
- Keep real names in the **Local Config**: `config/game_config.local.json` (gitignored)

Create your private config once:

```bash
cp config/game_config.example.json config/game_config.local.json
# then edit config/game_config.local.json with real names
```

## CLI

Initialize Local Config from Example Config:

```bash
uv run formation-graphics init-config
```

Generate Match Plan with Heuristic Strategy:

```bash
uv run formation-graphics heuristic --config config/game_config.local.json
```

Generate Match Plan with Solver Strategy:

```bash
uv run formation-graphics solver --config config/game_config.local.json
```

Generate a Solver plan with 5-minute blocks:

```bash
uv run formation-graphics solver --config config/game_config.local.json --preset five-minute
```

Generate calmer Solver plans that trade some fairness for fewer changes:

```bash
uv run formation-graphics solver --config config/game_config.local.json --preset steady
uv run formation-graphics solver --config config/game_config.local.json --preset compromise
```

Generate a lower-chaos Solver plan with fewer, longer substitution blocks:

```bash
uv run formation-graphics solver --config config/game_config.local.json --preset low-chaos
```

Open generated Segment Graphics automatically:

```bash
uv run formation-graphics heuristic --config config/game_config.local.json --open
uv run formation-graphics solver --config config/game_config.local.json --open
```

Solver Strategy Bench Stint Cap tuning:

```bash
uv run formation-graphics solver --max-consecutive-bench 1
```

Published artifacts are written to `output/<game_id>/`, `output/<game_id>_solver/`, and preset-specific solver directories such as `output/<game_id>_solver_steady/`, `output/<game_id>_solver_compromise/`, `output/<game_id>_solver_five_minute/`, or `output/<game_id>_solver_low_chaos/`.

## Local web API

Run the FastAPI backend and browser UI:

```bash
uv run formation-graphics-web
```

Then open:

```text
http://127.0.0.1:8000/
```

Useful endpoints:

```text
GET  /api/health
GET  /api/presets
POST /api/solve
```

Example solve request body:

```json
{
  "config": { "game_id": "...", "game_minutes": 40, "players": {}, "gk1": "...", "gk2": "...", "kickoff_starters": [] },
  "preset": "compromise",
  "max_consecutive_bench": 1
}
```

## Dev niceties

Run tests with pytest:

```bash
uv run pytest
```

Lint and format with Ruff:

```bash
uv run ruff check .
uv run ruff format .
```

