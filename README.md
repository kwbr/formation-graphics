# Formation Graphics (7v7)

Generate substitution/formation graphics, CSV schedules, player stats, and A4 printable half sheets.

## Privacy-safe config workflow

- Commit only: `config/game_config.example.json`
- Keep real names in: `config/game_config.local.json` (gitignored)

Create your private config once:

```bash
cp config/game_config.example.json config/game_config.local.json
# then edit config/game_config.local.json with real names
```

## Run

Heuristic scheduler:

```bash
uv run main.py --config config/game_config.local.json
```

Solver scheduler:

```bash
uv run solver_schedule.py --config config/game_config.local.json
```

Open generated images automatically:

```bash
uv run main.py --config config/game_config.local.json --open
uv run solver_schedule.py --config config/game_config.local.json --open
```

Outputs are written to `output/<game_id>/` and `output/<game_id>_solver/`.
