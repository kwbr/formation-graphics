# Ubiquitous Language

## Match structure

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Match** | One 40-minute game that is split into two 20-minute halves. | Game day, session |
| **Half** | One of the two 20-minute phases of a Match. | Halftime period |
| **Halftime** | The boundary at minute 20 where keeper assignment switches. | Natural sub break |
| **Global Block** | The canonical substitution interval across the full Match timeline, which may cross Halftime. | Half block, fixed-half block |
| **Half Segment** | The portion of a Global Block that lies inside one Half. | Block (when half-specific), slice |

## Players and roles

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Player** | A named child available for selection in a Match lineup. | Kid, slot |
| **Keeper 1 (gk1)** | The player assigned as GK for Half 1 and outfield for Half 2. | First-half goalie (without identifier) |
| **Keeper 2 (gk2)** | The player assigned as outfield for Half 1 and GK for Half 2. | Second-half goalie (without identifier) |
| **Non-keeper** | Any Player who is neither Keeper 1 nor Keeper 2. | Field-only player |
| **Kickoff Starters** | Exactly seven Players on field at minute 0, including both keepers (one in goal, one outfield). | Starters (ambiguous), starting pool |

## Formation and movement

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **2-3-1 Formation** | The outfield shape with LB, RB, LM, CM, RM, and ST plus GK. | Generic 7v7 shape |
| **Position Preference** | An ordered list of outfield positions preferred by a Player. | Single best position |
| **Mirror Fallback** | Side-swap fallback between LB↔RB and LM↔RM with small penalty. | Any-side swap |
| **Substitution Boundary** | A time boundary where lineup changes are allowed. | Rolling anytime |
| **Incoming Player** | A Player on field now who was off field in the previous segment. | Subbed in (without reference segment) |
| **Position Change** | A Player remains on field across adjacent segments but is assigned a different position. | Move, shuffle |
| **Bench Stint** | A consecutive run of Global Blocks where a Non-keeper is off field. | Rest spell |

## Scheduling objectives

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Fair Minutes** | Equal or near-equal outfield minutes among Non-keepers. | Everyone equal (including keepers) |
| **Fairness Band** | Allowed deviation in Global Block play counts around target (default floor/ceil target). | Loose fairness |
| **Position Stability** | Minimizing Position Changes across adjacent segments. | Static lineup |
| **Bench Stint Cap** | Maximum consecutive benched Global Blocks for a Non-keeper. | No long bench (without numeric bound) |

## Output artifacts

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Block Graphic** | One lineup image for a Half Segment. | Formation image (ambiguous) |
| **Half Sheet (A4)** | A printable one-page-per-half grid of block graphics. | Printout |
| **Schedule CSV** | Tabular lineup-by-segment output with absolute and half-relative times. | Rotation list |
| **Player Stats CSV** | Per-player totals for minutes, GK/outfield split, and bench/played counts. | Summary table |

## Relationships

- A **Match** contains exactly two **Halves**.
- A **Match** timeline is partitioned into **Global Blocks**.
- A **Global Block** maps to one or two **Half Segments**.
- A **Half Segment** has exactly one **lineup** of 7 Players: 1 **GK** and 6 outfield positions in **2-3-1 Formation**.
- **Keeper 1** is GK in Half 1 and outfield in Half 2; **Keeper 2** is outfield in Half 1 and GK in Half 2.
- A **Kickoff Starters** set contains exactly 7 Players and must include both keepers.
- **Fair Minutes** applies to **Non-keepers** only.
- A **Bench Stint Cap** constrains consecutive off-field **Global Blocks** for each **Non-keeper**.

## Example dialogue

> **Dev:** "If a **Global Block** crosses **Halftime**, do we force a substitution at 20:00?"
>
> **Domain expert:** "No. The same rotating group continues; only keeper assignment flips from **Keeper 1** to **Keeper 2** in goal."
>
> **Dev:** "So fairness is measured with **Fair Minutes** for **Non-keepers**, while both keepers stay on for the full **Match**?"
>
> **Domain expert:** "Exactly. Keepers are exempt from non-keeper fairness, and we enforce a **Bench Stint Cap** so nobody sits too long."
>
> **Dev:** "And if someone stays on but moves LB to CM, that is a **Position Change**, not an **Incoming Player**?"
>
> **Domain expert:** "Correct — incoming and position-change markers are distinct in each **Block Graphic** and on the **Half Sheet (A4)**."

## Flagged ambiguities

- "block" was used for both full-match substitution intervals and half-only chunks. Use **Global Block** for full timeline intervals and **Half Segment** for half-specific portions.
- "starters" was used as both a priority list and exact kickoff lineup. Use **Kickoff Starters** only for the exact 7 at minute 0.
- "fair share" was used to mean both equal minutes and short waits. Keep these separate: **Fair Minutes** vs **Bench Stint Cap**.
- "halftime as a natural block" conflicted with crossing-block behavior. Canonical rule: **Global Blocks** may cross Halftime.
- "on the field all the time" was initially specified for one keeper, then both. Canonical rule: both **Keeper 1** and **Keeper 2** play full Match time.
