# College Football Playoff Predictor (2026)

An automated data pipeline that predicts the College Football Playoff field — which 12 teams
make it and how they're seeded — using only game results and team ratings. Built to show what
data can do, not for betting.

**What it does:** every Tuesday during the season, GitHub Actions pulls fresh results from the
CollegeFootballData API, cleans and validates them, rebuilds each team's résumé, and predicts the
committee's playoff field, applying the actual selection rules.

## Current prediction

<!-- PREDICTION:START -->
*Updated 2026-10-27 · ranking week 9 · champions are projected from current standings until title games are played.*

| Seed | Team | Conference | Record | Why they're in |
|---:|---|---|---|---|
| 1 | Indiana | Big Ten | 7-1 | at-large |
| 2 | Miami | ACC | 7-0 | ACC champion |
| 3 | Ohio State | Big Ten | 6-1 | Big Ten champion |
| 4 | Kentucky | SEC | 7-1 | SEC champion |
| 5 | Georgia | SEC | 6-1 | at-large |
| 6 | Utah | Big 12 | 7-0 | Big 12 champion |
| 7 | UCLA | Big Ten | 7-0 | at-large |
| 8 | Texas | SEC | 5-2 | at-large |
| 9 | Alabama | SEC | 6-2 | at-large |
| 10 | Northwestern | Big Ten | 6-1 | at-large |
| 11 | BYU | Big 12 | 6-1 | at-large |
| 12 | Boise State | Pac-12 | 6-1 | highest-ranked other champion |

Seeds 1–4 get first-round byes. 2026 seeding is assumed to follow the ranking (see Limitations).
<!-- PREDICTION:END -->

## Pipeline

```
CFBD API ──► ingest ──► clean ──► features ──► model ──► playoff rules ──► prediction
            raw CSVs   validated   one resume    blend of    auto-bids &      data/results/
                       team-games  per team/week 3 models    seeding
                          │                          ▲
                    197+ tests (incl. a leakage test)│  walk-forward backtest
```

| Step | File | What it does |
|---|---|---|
| Ingest | `src/ingest.py` | Pulls games and rankings, with retry/backoff on API errors |
| Clean | `src/clean.py` | Keeps FBS games, drops and logs bad scores, one row per team per game, fixes a verified source error |
| Features | `src/features.py` | Builds each team's résumé *as of each committee week* using only games already played |
| Model | `src/model.py` | Ridge + gradient boosting + logistic blend; walk-forward backtest |
| Rules | `src/field.py` | Turns a ranking into the 12-team field under the 2024, 2025 and 2026 rules |
| Automation | `.github/workflows/refresh.yml` | Weekly: ingest → clean → features → predict → test → commit |

## How well does it work?

Tested **walk-forward**: to predict a season, the model trains only on earlier seasons. Scores are
for Selection Day, averaged over 8 seasons (2017–2025, excluding COVID-affected 2020).

| Method | Top 12 right (of 12) | Top 4 right (of 4) | Avg. seed error |
|---|---|---|---|
| AP poll (a human poll, for reference) | 11.6 | 3.8 | 0.6 |
| **This model (blend)** | **10.8** | **3.5** | **1.3** |
| Record, then schedule strength | 9.6 | 3.0 | 1.9 |
| Elo rating alone | 9.0 | 2.5 | 2.2 |

The model uses **no human polls and no team names** as inputs — only results, margins, schedule
strength, and opponent quality. Adding the playoff selection rules (auto-bids for conference
champions) raised the average from 10.50 to 10.75 on a 2026-rules replay of the same seasons, and
fixed the first-round-bye picks in 2024 (2 of 4 → 4 of 4).

### Findings

- **Does old data help, given roster turnover?** Training on all prior seasons did as well as, or
  slightly better than, training on only the last three. The model learns how the *committee*
  turns a résumé into a ranking, which changes far more slowly than rosters do.
- **Where it misses:** almost entirely bubble teams (committee #10–#16). Several misses were
  conference champions, which led to building the rules engine.
- **Conference-record features didn't help** (10.75 vs 10.75), so they're built but not used.
  Auto-bids are handled as explicit rules instead.

## Data integrity

- **No leakage.** A ranking labeled "week W" comes out after week W−1's games, so only those
  games are used; postseason games never are. A test checks every team's game count in every
  snapshot, and a date cutoff handles the one season (2019) where week numbering overlaps.
- **Rules are verified against reality.** `tests/test_field.py` checks that the code reproduces
  the real 2024 and 2025 playoff fields and seeds from the committee's rankings.
- **Source errors are corrected openly.** CFBD lists the 2023 final ranking as "5, 5, 7" (no #6);
  the official release has Florida State #5, Georgia #6. The fix is a small documented table in
  `src/clean.py`, not a silent edit.

## Limitations (read these)

- **Early-season predictions are rough.** The model learned from committee weeks (week 10+). Its
  week-8 picks haven't been backtested, and conference champions are *projected* from current
  standings until the title games are played.
- **2026 seeding is assumed.** The August 2026 format announcement doesn't describe seeding, so
  seeds follow the ranking as in 2025. The 2026 auto-bid rule has no real results to test on yet.
- **Small sample.** Eight test seasons means differences of about 0.3 teams between model
  variants are noise.
- **It can't see** injuries, quarterback changes, or the committee's judgment calls.

## Run it yourself

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # paste your free key from collegefootballdata.com
python -m src.ingest --years 2014-2026
python -m src.clean --years 2014-2026
python -m src.features --years 2014-2026
python -m src.model backtest          # walk-forward results
python -m src.model field-backtest    # model + playoff rules vs. the true fields
python -m src.model predict           # current 2026 field -> data/results/
python -m pytest
```

Weekly predictions are saved in `data/results/history/` so they can be scored against the
committee's rankings once those start in November.

Data: [CollegeFootballData.com](https://collegefootballdata.com). Original exploratory analysis
that started this project: `footballthing.Rmd`.
