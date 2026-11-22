# College Football Playoff Predictor (2026)

An automated data pipeline that predicts the College Football Playoff field — which 12 teams
make it and how they're seeded — using only game results and team ratings. Built to show what
data can do, not for betting.

**What it does:** every Tuesday during the season, GitHub Actions pulls fresh results from the
CollegeFootballData API, cleans and validates them, rebuilds each team's résumé, and predicts the
committee's playoff field, applying the actual selection rules.

## Current prediction

<!-- PREDICTION:START -->
*Updated 2026-11-22 · ranking week 13 · champions are projected from current standings until title games are played.*

| Seed | Team | Conference | Record | Why they're in |
|---:|---|---|---|---|
| 1 | Utah | Big 12 | 10-0 | Big 12 champion |
| 2 | Georgia | SEC | 9-1 | SEC champion |
| 3 | Texas | SEC | 9-2 | at-large |
| 4 | Miami | ACC | 9-1 | ACC champion |
| 5 | Alabama | SEC | 9-2 | at-large |
| 6 | Notre Dame | FBS Independents | 9-1 | Notre Dame (ranked top 12) |
| 7 | Tennessee | SEC | 9-2 | at-large |
| 8 | Indiana | Big Ten | 9-2 | at-large |
| 9 | Wake Forest | ACC | 10-1 | at-large |
| 10 | UCLA | Big Ten | 10-1 | Big Ten champion |
| 11 | Oregon | Big Ten | 8-3 | at-large |
| 12 | Boise State | Pac-12 | 9-1 | highest-ranked other champion |

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
| Weekly forecast | `src/forecast.py` | Model v3: forecasts the committee's *next* list from the results plus its last list, saves it before release, scores it afterwards |
| Simulation | `src/simulate.py` | Plays the rest of the season thousands of times for field / bye / champion odds |
| Scorecard | `src/scorecard.py` | Scores the frozen model (tag `model-v1`) against each real committee list |
| Automation | `.github/workflows/refresh.yml` | Weekly: ingest → clean → features → predict → test → commit |

## Next committee list: weekly forecast

<!-- FORECAST:START -->
**Forecast of the committee's week 13 list**, made 2026-11-22 from this week's results and the
committee's last list. It is saved before the list is released, then scored below.

| Predicted rank | Team | Record | Committee's last rank |
|---:|---|---|---:|
| 1 | Utah | 10-0 | 2 |
| 2 | Georgia | 9-1 | 1 |
| 3 | Texas | 9-2 | 5 |
| 4 | Miami | 9-1 | 7 |
| 5 | Notre Dame | 9-1 | 6 |
| 6 | Alabama | 9-2 | 3 |
| 7 | Tennessee | 9-2 | 9 |
| 8 | UCLA | 10-1 | 4 |
| 9 | Indiana | 9-2 | 8 |
| 10 | Wake Forest | 10-1 | 11 |
| 11 | Texas Tech | 10-1 | 12 |
| 12 | BYU | 9-2 | 10 |
| 13 | Oregon | 8-3 | 13 |
| 14 | Boise State | 9-1 | 17 |
| 15 | Iowa | 9-2 | 15 |

**Scored forecasts** (top 12 correct out of 12):

*None yet. The first forecast is scored once the committee releases its list.*

*Backtest, 39 past committee lists forecast one week ahead:* v3 11.2/12, résumé model 10.8/12, repeat-last-list 10.9/12. v3 beat v1 on 14 lists, tied on 23, lost on 2 (gain +0.36 teams, 3.4 standard errors).
<!-- FORECAST:END -->

## Who makes the field? (simulated odds)

<!-- SIMULATION:START -->
*500 simulations of the rest of the regular season and the conference title games, updated 2026-11-22.*

| Team | Record | Games left | Makes the field | First-round bye | Wins conference |
|---|---|---:|---:|---:|---:|
| Georgia | 9-1 | 2 | 100% | 91% | 60% |
| Texas | 9-2 | 1 | 100% | 78% | 32% |
| Notre Dame | 9-1 | 2 | 100% | 9% | 0% |
| Miami | 9-1 | 2 | 96% | 48% | 49% |
| Alabama | 9-2 | 1 | 95% | 9% | 8% |
| Utah | 10-0 | 2 | 92% | 61% | 55% |
| Wake Forest | 10-1 | 1 | 88% | 37% | 51% |
| Tennessee | 9-2 | 1 | 79% | 1% | 0% |
| Indiana | 9-2 | 1 | 76% | 51% | 63% |
| Iowa | 9-2 | 1 | 70% | 2% | 3% |
| Oregon | 8-3 | 1 | 61% | 12% | 20% |
| BYU | 9-2 | 1 | 55% | 0% | 0% |
| Boise State | 9-1 | 1 | 50% | 0% | 50% |
| Texas Tech | 10-1 | 1 | 50% | 0% | 45% |
| UCLA | 10-1 | 1 | 24% | 0% | 14% |
| Liberty | 10-1 | 1 | 18% | 0% | 84% |
| USC | 8-3 | 1 | 15% | 0% | 0% |
| New Mexico | 9-2 | 1 | 15% | 0% | 59% |
| UTSA | 8-2 | 2 | 7% | 0% | 16% |
| Texas State | 7-4 | 0 | 5% | 0% | 50% |
| James Madison | 8-3 | 1 | 4% | 0% | 21% |
| Air Force | 9-2 | 1 | 1% | 0% | 4% |

These capture game-to-game luck only; they assume the model's ranking is what the committee will do.
In backtests they were accurate at the extremes and mildly overconfident in the middle (see below).
<!-- SIMULATION:END -->

## Live scorecard (2026)

<!-- SCORECARD:START -->
Committee's real top 12 vs. the model. **v1** was frozen on Oct 17 (git tag `model-v1`), before the
committee's first 2026 list. **v2** adds conference strength and was designed after week 12, so
weeks marked * are not a fair test of v2 and are left out of its average.

| Committee week | v1: top 12 right | v2: top 12 right | AP poll: top 12 right | v1: top 4 right |
|---:|---:|---:|---:|---:|
| 10 | 11 / 12 | 11* / 12 | 12 / 12 | 4 / 4 |
| 11 | 10 / 12 | 10* / 12 | 11 / 12 | 2 / 4 |
| 12 | 10 / 12 | 10* / 12 | 12 / 12 | 2 / 4 |
| **Average** | **10.3 / 12** | **not enough weeks yet** | **11.7 / 12** | **2.7 / 4** |

Latest list (week 12): v1 missed BYU; Texas Tech; v1 wrongly included Boise State; Oregon.
<!-- SCORECARD:END -->

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

### Are the simulated odds trustworthy?

Backtested on 7 past seasons (2017, 2018, 2021–2025): rewind to two committee weeks before
Selection Day, simulate with only the information available then, and a model trained only on
earlier seasons. `python -m src.simulate_backtest` reproduces this.

| Simulated chance of making the field | Team-seasons | Predicted | Actually made it |
|---|---:|---:|---:|
| about 0% | 793 | 0% | 0.4% |
| 5–20% | 20 | 13% | 20% |
| 20–40% | 21 | 29% | 14% |
| 40–60% | 20 | 49% | 50% |
| 60–80% | 10 | 70% | 60% |
| 80–95% | 12 | 89% | 92% |
| 95–100% | 48 | 99% | 98% |

- **It beats a plain yes/no prediction:** Brier score 0.020 vs 0.028 for the field, and 0.012 vs
  0.020 for first-round byes (lower is better).
- **Be cautious in the middle.** Those buckets hold only 10–21 team-seasons each, and two were
  overconfident. Bye odds are noisier than field odds.
- **What it ignores:** the committee's own unpredictability beyond the model, injuries, and real
  conference tiebreakers for the title games (it uses conference record, then Elo).

### Findings

- **Does old data help, given roster turnover?** Training on all prior seasons did as well as, or
  slightly better than, training on only the last three. The model learns how the *committee*
  turns a résumé into a ranking, which changes far more slowly than rosters do.
- **Where it misses:** almost entirely bubble teams (committee #10–#16). Several misses were
  conference champions, which led to building the rules engine.
- **Investigating the 2026 misses (BYU, Texas Tech).** They are bubble noise, not a pattern: the model
  had them 13th and 15th against the committee's 10th and 12th, and measured on Big 12 teams alone
  the historical bias is about zero. The one real, repeatable flaw was over-rating Group of 5 teams
  (37% of the model's Group of 5 top-15 picks were teams the committee didn't rank top 20, e.g.
  Boise State in 2026). Adding conference strength (**model v2**) cut that to 26% and added about
  0.09 correct picks per week (~1.7 standard errors), so it is promising but not proven. A
  strength-of-record feature added nothing measurable and was dropped. v1 stays frozen; v2 is scored
  alongside it on future committee lists.
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
