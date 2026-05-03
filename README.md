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

## CLI

Initialize private config from template:

```bash
uv run formation-graphics init-config
```

Heuristic scheduler:

```bash
uv run formation-graphics heuristic --config config/game_config.local.json
```

Solver scheduler:

```bash
uv run formation-graphics solver --config config/game_config.local.json
```

Open generated images automatically:

```bash
uv run formation-graphics heuristic --config config/game_config.local.json --open
uv run formation-graphics solver --config config/game_config.local.json --open
```

Solver bench-stint tuning:

```bash
uv run formation-graphics solver --max-consecutive-bench 1
```

Outputs are written to `output/<game_id>/` and `output/<game_id>_solver/`.

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

