# Ubiquitous Language

## Match structure

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Match** | One 40-minute game split into two 20-minute Halves. | Session, game day |
| **Half** | One of the two time phases of a Match. | Period |
| **Halftime** | The minute-20 boundary where keeper assignment flips. | Natural sub break |
| **Global Block** | The canonical substitution interval across the full Match timeline. | Block (ambiguous), half block |
| **Half Segment** | The portion of a Global Block that lies in one Half. | Slice, half block |

## Players and roles

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Player** | A named child eligible for lineup assignment in a Match. | Kid, slot |
| **Keeper 1 (gk1)** | The Player assigned GK in Half 1 and outfield in Half 2. | First-half goalie |
| **Keeper 2 (gk2)** | The Player assigned outfield in Half 1 and GK in Half 2. | Second-half goalie |
| **Non-keeper** | Any Player who is neither Keeper 1 nor Keeper 2. | Field-only player |
| **Kickoff Starters** | The exact seven Players on field at minute 0, including both keepers. | Starters, starting pool |

## Formation and movement

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **2-3-1 Formation** | The outfield layout LB, RB, LM, CM, RM, ST plus GK. | Generic 7v7 shape |
| **Position Preference** | A set of outfield positions a Player is comfortable playing. The JSON list order is not meaningful. | Best position, ranked preference |
| **Mirror Fallback** | Side-swap fallback LB↔RB and LM↔RM with lower priority than explicit Position Preference. | Any-side swap |
| **Incoming Player** | A Player on field now who was off field in the previous Half Segment. | Subbed in |
| **Position Change** | A Player on field in consecutive Half Segments but in different positions. | Shuffle, move |
| **Bench Stint** | A consecutive run of Global Blocks where a Non-keeper is off field. | Rest spell |

## Planning and fairness

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Match Plan** | The planned sequence of Half Segments and lineups for one Match. | Rotation output |
| **Planning Strategy** | The method used to produce a Match Plan. | Mode |
| **Heuristic Strategy** | A deterministic rule-based Planning Strategy. | Default logic |
| **Solver Strategy** | A constraint-optimization Planning Strategy (CP-SAT). | AI planner |
| **Fair Minutes** | Equal or near-equal outfield minutes among Non-keepers. | Equal minutes for everyone |
| **Fairness Band** | Allowed Global Block deviation around target Non-keeper play counts. | Loose fairness |
| **Position Stability** | Minimization of Position Changes across adjacent Half Segments. | Static lineup |
| **Bench Stint Cap** | Maximum allowed consecutive benched Global Blocks for a Non-keeper. | No long bench |

## Configuration and outputs

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Match Config** | The validated match input model containing roster, keeper assignments, and starter set. | Raw config dict |
| **Local Config** | Private Match Config containing real player names and excluded from public VCS. | Main config |
| **Example Config** | Public anonymized Match Config template for repository sharing. | Dummy config |
| **Segment Graphic** | One rendered lineup image for one Half Segment. | Block graphic |
| **Half Sheet (A4)** | A one-page printable layout of all Segment Graphics for one Half. | Printout |
| **Schedule CSV** | Tabular output listing lineup and timing per Half Segment. | Rotation list |
| **Player Stats CSV** | Per-player totals for total, GK, outfield, and bench/played segment counts. | Summary table |

## Relationships

- A **Match** contains exactly two **Halves**.
- A **Match** timeline is partitioned into **Global Blocks**.
- A **Global Block** maps to one or two **Half Segments**.
- A **Half Segment** has exactly one lineup of 7 Players: 1 GK and 6 outfield positions in **2-3-1 Formation**.
- **Keeper 1** is GK in Half 1 and outfield in Half 2; **Keeper 2** is outfield in Half 1 and GK in Half 2.
- A **Kickoff Starters** set contains exactly 7 Players and includes both keepers.
- A **Match Config** produces one **Match Plan** through a chosen **Planning Strategy**.
- A **Match Plan** produces **Segment Graphics**, **Half Sheet (A4)** pages, **Schedule CSV**, and **Player Stats CSV**.
- **Fair Minutes** applies only to **Non-keepers**.

## Example dialogue

> **Dev:** "For this **Match Config**, should we run **Heuristic Strategy** or **Solver Strategy**?"
>
> **Domain expert:** "Use **Solver Strategy** when we need tighter **Position Stability** and a strict **Bench Stint Cap**."
>
> **Dev:** "If a **Global Block** crosses **Halftime**, does that create two **Half Segments** in the **Match Plan**?"
>
> **Domain expert:** "Yes, and keeper assignment flips between those segments while the rotating group stays aligned."
>
> **Dev:** "Then the publish step should generate **Segment Graphics**, one **Half Sheet (A4)** per Half, plus **Schedule CSV** and **Player Stats CSV**?"
>
> **Domain expert:** "Exactly — those outputs are the canonical artifacts of the Match Plan."

## Flagged ambiguities

- "block" was used for both full-match intervals and half-scoped segments; use **Global Block** vs **Half Segment**.
- "starters" was used as both a priority concept and exact kickoff set; use **Kickoff Starters** only for the exact seven at minute 0.
- "fair share" was used to mean both equal minutes and shorter waits; keep **Fair Minutes** separate from **Bench Stint Cap**.
- "config" was used for both public template and private roster; distinguish **Example Config** from **Local Config**.
- "plan" was used for tactical coaching intent and software output; in code/workflow use **Match Plan** for the generated schedule artifact.
