# College Football Playoff Predictor (2026)

> **In one sentence:** this project uses data (and nothing else) to predict which 12 college
> football teams will be invited to the 2026 national-championship playoff, then checks its own
> predictions against the real decisions every week.

It is a hobby and portfolio project, **not for betting**. This page rebuilds itself automatically
every Sunday and Wednesday during the season, so everything below is current as of the "updated"
date shown in each section.

---

## New to college football? Start here (60 seconds)

**The basic idea.** About 136 college teams play in the top level of the sport. At the end of each
season, **12 of them are invited to a single-elimination tournament, the "playoff,"** that decides the
national champion. A small group of people picks the 12, not a formula. That is what makes it
interesting to predict with data.

| Word you'll see | What it means |
|---|---|
| **The committee** | About a dozen people who rank the best 25 teams every week from early November. Their final list, on **Selection Sunday (Dec 6, 2026)**, decides the 12 invited teams. |
| **The field** | The 12 teams invited to the playoff. |
| **Seed** | A team's number in the tournament (1 to 12). **Seeds 1–4 get a "bye"**: they skip the first round. |
| **Record** | Wins and losses. "9-1" means 9 wins, 1 loss. |
| **Conference** | A group of teams that play each other (SEC, Big Ten, Big 12, ACC and others). Each ends its season with a **title game**; the winner is the conference **champion**. |
| **Automatic spot** | A guaranteed place in the field. In 2026: the champions of the SEC, Big Ten, Big 12 and ACC, the best champion from any other conference, and Notre Dame if it is ranked in the top 12. |
| **At-large spot** | Every other place in the field, filled by the highest-ranked remaining teams. |
| **Schedule strength** | How good a team's opponents were. Going 10-0 against weak teams is less impressive than 9-1 against strong ones. |
| **Big win** | A win over a team in the top fifth of the sport. |
| **Power rating (Elo)** | One number for how strong a team is, updated after every game (like a chess rating). |
| **AP poll** | A weekly ranking voted on by sports writers. Used here as a human benchmark. |
| **Bubble** | The teams right at the cut line: could easily be in or out. |
| **Model** | The computer program that turns each team's results into a predicted ranking. |

---

## How to read this page

Each section below has two parts: **a table with the prediction**, and a **"Why?" explanation** in
plain words. Both are written by the code from the latest data (not typed by hand), so they always
match each other and update with every refresh.

There are three kinds of prediction, answering three different questions:

1. **If the season ended today, who would be in?**
2. **What will the committee announce next Tuesday?**
3. **How likely is each team to make it by the end?**

And a fourth section keeps score: how often has the model been right against the real committee?

---

## 1. If the season ended today, who would make the playoff?

The model ranks every team using only results. Then the real selection rules are applied: first the
automatic spots, then the highest-ranked remaining teams.

<!-- PREDICTION:START -->
*Updated 2026-11-22 · ranking week 13 · champions are projected from current standings until title games are played.*

| Seed | Team | Conference | Record | Why they're in |
|---:|---|---|---|---|
| 1 | Utah | Big 12 | 11-0 | Big 12 champion |
| 2 | Georgia | SEC | 10-1 | SEC champion |
| 3 | Texas | SEC | 9-2 | at-large |
| 4 | Miami | ACC | 10-1 | ACC champion |
| 5 | Notre Dame | FBS Independents | 10-1 | Notre Dame (ranked top 12) |
| 6 | Alabama | SEC | 9-2 | at-large |
| 7 | Indiana | Big Ten | 9-2 | at-large |
| 8 | Tennessee | SEC | 9-2 | at-large |
| 9 | Wake Forest | ACC | 10-1 | at-large |
| 10 | Oregon | Big Ten | 8-3 | at-large |
| 11 | UCLA | Big Ten | 10-1 | Big Ten champion |
| 12 | Boise State | Pac-12 | 9-2 | highest-ranked other champion |

Seeds 1–4 get first-round byes. 2026 seeding is assumed to follow the ranking (see Limitations).

**Why these 12?**

- **Automatic spots** go to conference champions, no matter how they rank: Utah (Big 12 champion), Georgia (SEC champion), Miami (ACC champion), Notre Dame (ranked top 12), UCLA (Big Ten champion), Boise State (highest-ranked other champion). Until the conference title games are played, each "champion" here is just the current leader.
- **The remaining spots** go to the highest-ranked teams (by the model) that aren't already in.
- An automatic spot can beat a better-ranked team: Boise State (ranked 18th) is in on the champion rule alone, which takes a spot from an at-large team.
- **The closest call:** **Oregon** (8-3) is the last team in; **Texas Tech** (10-1) is the first team out. Oregon has a harder schedule (12th vs 80th hardest) and more big wins (4 vs 1). Texas Tech has fewer losses (1 vs 3) and bigger typical winning margins.

<details><summary>Each team's résumé</summary>

| Seed | Team | Résumé |
|---:|---|---|
| 1 | Utah | 11-0, 57th-hardest schedule of 138, 2 big wins (best: Arizona) |
| 2 | Georgia | 10-1, 22nd-hardest schedule of 138, 4 big wins (best: Alabama) |
| 3 | Texas | 9-2, 2nd-hardest schedule of 138, 5 big wins (best: Ohio State) |
| 4 | Miami | 10-1, 40th-hardest schedule of 138, 2 big wins (best: Wake Forest) |
| 5 | Notre Dame | 10-1, 58th-hardest schedule of 138, 1 big win (best: Miami) |
| 6 | Alabama | 9-2, 17th-hardest schedule of 138, 1 big win (best: LSU) |
| 7 | Indiana | 9-2, 31st-hardest schedule of 138, 3 big wins (best: USC) |
| 8 | Tennessee | 9-2, 19th-hardest schedule of 138, 2 big wins (best: Alabama) |
| 9 | Wake Forest | 10-1, 83rd-hardest schedule of 138, 1 big win (best: Louisville) |
| 10 | Oregon | 8-3, 12th-hardest schedule of 138, 4 big wins (best: Ohio State) |
| 11 | UCLA | 10-1, 74th-hardest schedule of 138, 1 big win (best: Oregon) |
| 12 | Boise State | 9-2, 69th-hardest schedule of 138, 0 big wins |

*Big win = a win over a team in the top fifth of the sport by power rating.*
</details>
<!-- PREDICTION:END -->

---

## 2. What will the committee announce next Tuesday?

The committee rarely changes its mind much from week to week, so this forecast starts from its
last list and then adjusts for the weekend's results. **Each forecast is saved before the committee
publishes**, then scored once the real list comes out (see the git history for the timestamps).

<!-- FORECAST:START -->
**Forecast of the committee's week 13 list**, made 2026-11-22 from this week's results and the
committee's last list. It is saved before the list is released, then scored below.

| Predicted rank | Team | Record | Committee's last rank |
|---:|---|---|---:|
| 1 | Utah | 11-0 | 2 |
| 2 | Georgia | 10-1 | 1 |
| 3 | Texas | 9-2 | 5 |
| 4 | Miami | 10-1 | 7 |
| 5 | Notre Dame | 10-1 | 6 |
| 6 | Alabama | 9-2 | 3 |
| 7 | Indiana | 9-2 | 8 |
| 8 | Tennessee | 9-2 | 9 |
| 9 | Wake Forest | 10-1 | 11 |
| 10 | UCLA | 10-1 | 4 |
| 11 | Texas Tech | 10-1 | 12 |
| 12 | BYU | 9-2 | 10 |
| 13 | Oregon | 8-3 | 13 |
| 14 | Iowa | 9-2 | 15 |
| 15 | USC | 8-3 | 18 |

**Why does the forecast look like this?**

- The committee rarely changes its mind much, so the forecast starts from its last list. 9 of the top 12 are predicted to land within two spots of where the committee already had them (0 in the exact same spot).
- Then it adjusts for this week's results. The biggest expected moves in the top 25:
  - **UCLA** down 6 to 10 (was 4): lost 16-18 at Michigan.
  - **Ole Miss** up 5 to 20 (was 25): won 59-17 vs Wofford.
  - **Houston** down 4 to 24 (was 20): won 34-31 at West Virginia.
  - **Alabama** down 3 to 6 (was 3): won 47-0 vs Chattanooga.
  - **Miami** up 3 to 4 (was 7): won 28-20 vs Virginia Tech.
  - **Oklahoma** up 3 to 19 (was 22): won 28-7 vs Texas A&M.

**Scored forecasts** (top 12 correct out of 12):

*None yet. The first forecast is scored once the committee releases its list.*

*Backtest, 39 past committee lists forecast one week ahead:* v3 11.2/12, résumé model 10.8/12, repeat-last-list 10.9/12. v3 beat v1 on 14 lists, tied on 23, lost on 2 (gain +0.36 teams, 3.4 standard errors).
<!-- FORECAST:END -->

---

## 3. How likely is each team to make the playoff?

Nobody knows how the last games will go, so the computer **plays out the rest of the season
thousands of times** (using each team's strength to decide who wins), picks the field each time, and
counts how often each team makes it. The "if they win out" and "if they lose" columns show how much
the final games matter.

<!-- SIMULATION:START -->
*500 simulations of the rest of the regular season and the conference title games, updated 2026-11-22.*

| Team | Record | Games left | Makes the field | If they win out | If they lose at least once | First-round bye | Wins conference |
|---|---|---:|---:|---:|---:|---:|---:|
| Georgia | 10-1 | 1 | **100%** | 100% | – | 99% | 66% |
| Texas | 9-2 | 1 | **100%** | 100% | 100% | 73% | 27% |
| Notre Dame | 10-1 | 1 | **100%** | 100% | – | 3% | 0% |
| Utah | 11-0 | 1 | **97%** | 100% | 45% | 75% | 57% |
| Miami | 10-1 | 2 | **96%** | 100% | 92% | 62% | 48% |
| Alabama | 9-2 | 1 | **95%** | 100% | 69% | 6% | 6% |
| Tennessee | 9-2 | 1 | **88%** | 100% | 39% | 0% | 1% |
| Indiana | 9-2 | 1 | **82%** | 84% | – | 49% | 66% |
| Wake Forest | 10-1 | 2 | **71%** | 100% | 50% | 28% | 52% |
| Iowa | 9-2 | 1 | **71%** | 96% | 1% | 2% | 4% |
| Oregon | 8-3 | 1 | **59%** | 74% | 1% | 4% | 18% |
| BYU | 9-2 | 1 | **54%** | 65% | 0% | 0% | 0% |
| Boise State | 9-2 | 2 | **47%** | 50% | 30% | 0% | 48% |
| Texas Tech | 10-1 | 1 | **45%** | 46% | 41% | 0% | 43% |
| UCLA | 10-1 | 1 | **23%** | 43% | 2% | 0% | 13% |
| USC | 8-3 | 1 | **20%** | 42% | 0% | 0% | 0% |
| UTSA | 9-2 | 1 | **15%** | 23% | 4% | 0% | 26% |
| New Mexico | 9-2 | 1 | **14%** | 21% | 0% | 0% | 58% |
| Texas State | 7-4 | 1 | **11%** | 13% | 5% | 0% | 52% |
| James Madison | 8-3 | 1 | **6%** | 6% | 0% | 0% | 21% |
| Air Force | 9-2 | 1 | **5%** | 17% | 0% | 0% | 13% |
| Liberty | 10-1 | 2 | **2%** | 3% | 0% | 0% | 81% |

These capture game-to-game luck only; they assume the model's ranking is what the committee will do.
In backtests they were accurate at the extremes and mildly overconfident in the middle (see below).

**What do these odds depend on?**

- **Nearly locked in (99%+):** Georgia, Texas, Notre Dame. Even a bad finish probably wouldn't cost them.
- **Boise State** (9-2, 2 games left): 47% overall, **50% if they win out**, 30% if they lose at least once.
- **BYU** (9-2, 1 game left): 54% overall, **65% if they win out**, 0% if they lose at least once.
- **Texas Tech** (10-1, 1 game left): 45% overall, **46% if they win out**, 41% if they lose at least once.
- **Oregon** (8-3, 1 game left): 59% overall, **74% if they win out**, 1% if they lose at least once.
- **Iowa** (9-2, 1 game left): 71% overall, **96% if they win out**, 1% if they lose at least once.
- **Wake Forest** (10-1, 2 games left): 71% overall, **100% if they win out**, 50% if they lose at least once.
- **Long shots that could sneak in by winning their conference:** Liberty. Under the 2026 rules the best champion from outside the big four conferences gets an automatic spot.
- Teams in the middle are the ones whose last games decide the field. Teams near 0% or 100% mostly won't move.
<!-- SIMULATION:END -->

**Can these odds be trusted?** I tested the same method on 7 past seasons, rewinding to two weeks
before Selection Day and using only what was known then:

| When the odds said | Teams | The odds predicted | What actually happened |
|---|---:|---:|---:|
| about 0% | 793 | 0% | 0.4% made it |
| 5–20% | 20 | 13% | 20% made it |
| 20–40% | 21 | 29% | 14% made it |
| 40–60% | 20 | 49% | 50% made it |
| 60–80% | 10 | 70% | 60% made it |
| 80–95% | 12 | 89% | 92% made it |
| 95–100% | 48 | 99% | 98% made it |

In plain terms: **at the extremes the odds were right** (teams given 95%+ made it 98% of the time,
teams near 0% almost never did). In the middle there are only 10–21 teams per row, and two rows
ran too confident, so treat mid-range odds as rough. The simulation also beat a plain yes/no
prediction on the standard accuracy score for forecasts.

---

## 4. How has the model done against the real committee?

This is the honest scoreboard. **Version 1** of the model was locked on **Oct 17**, before the
committee published any 2026 ranking (like writing predictions in a sealed envelope: I can't quietly
tweak them afterwards). The git tag `model-v1` proves it. Later versions are scored alongside it.

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

**Why did the model miss on week 12?**

- **The committee barely re-ranks.** Among teams on both of its last two lists, the typical team moved 1 spot and 9 of 22 didn't move at all. The model rebuilds its ranking from scratch each week, so it disagrees most about teams the committee is simply leaving alone.
- **In the committee's top 12 but not the model's:**
  - **BYU**: the committee has them 10th (was 10th last list); the model has them 13th. 8-2, 33rd-hardest schedule of 138, 2 big wins (best: Notre Dame).
  - **Texas Tech**: the committee has them 12th (was 12th last list); the model has them 15th. 9-1, 83rd-hardest schedule of 138, 1 big win (best: Arizona).
- **In the model's top 12 but not the committee's:**
  - **Boise State**: the model has them 11th; the committee has them 17th (was 24th last list). 9-1, 59th-hardest schedule of 138, 0 big wins.
  - **Oregon**: the model has them 12th; the committee has them 13th (was 16th last list). 7-3, 9th-hardest schedule of 138, 4 big wins (best: Ohio State).
<!-- SCORECARD:END -->

---

## How accurate is it, in general?

I tested the model on past seasons the way it would work in real life: **to predict a season, it
learned only from earlier seasons.** On Selection Sunday, averaged over 8 seasons (2017–2025,
skipping the 2020 COVID season):

| Method | Of the real 12 playoff teams, how many did it get right? | Of the real top 4? |
|---|---|---|
| AP poll (human writers, for reference) | 11.6 | 3.8 |
| **This model** | **10.8** | **3.5** |
| "Fewest losses, then schedule" rule of thumb | 9.6 | 3.0 |
| Power rating alone | 9.0 | 2.5 |

So the model gets roughly **11 of 12 teams right**, better than simple rules but not quite as good as
the human AP poll, which the committee tends to follow. The model uses **no human polls and no team
names**: only results, margins, schedule strength and opponent quality.

**What I learned from its mistakes:**

- **The committee barely re-ranks from week to week.** Copying the committee's *previous* list scored
  as well as the model did at predicting the *next* list. That discovery led to the weekly forecast
  in section 2 (Version 3), which beats the original on past lists (11.2 vs 10.8 of 12).
- **The model used to over-rate teams from smaller conferences** that pile up wins against weaker
  opponents (e.g. Boise State in 2026). Version 2 adds "how strong is this team's whole conference",
  which cut that mistake from 37% to 26% of cases. Promising, not proven.
- **Misses are almost always bubble teams** (ranked 10th–16th by the committee), where a couple of spots
  decide in or out. Two 2026 examples, BYU and Texas Tech, turned out to be ordinary bubble noise,
  not a hidden pattern.
- **Does old data help, given players change every year?** Yes: training on all past seasons did as
  well as, or slightly better than, only the last three. The model learns how *the committee* judges
  a résumé, which changes far more slowly than rosters do.

<details>
<summary><b>Technical details for the curious</b></summary>

- **Models.** Version 1 is an average of three models (ridge regression, gradient boosting, and a
  logistic classifier for "top 12") on 22 résumé features. Version 2 adds two conference-strength
  features. Version 3 adds the committee's previous rank as a feature.
- **Testing.** Walk-forward backtests: train on seasons before year *Y*, test on *Y*. With only 8
  test seasons, differences under about 0.3 teams between variants are noise. Paired
  comparisons (better/same/worse per season-week) are used to judge changes.
- **Version 2** was better on 5 of 47 season-weeks and worse on 1 (+0.09 teams, about 1.7
  standard errors). A strength-of-record feature was tested and dropped (no measurable gain).
- **Version 3** (next-list forecast) was better on 14 of 39 past lists and worse on 2
  (+0.36 teams, about 3.4 standard errors). The benefit fades to near zero three weeks ahead,
  so it is used only for the next-list forecast.
- **Simulator.** Game margin ~ Normal(0.0417 x Elo gap + 3.42 if home, sd 16.4), fitted on 2021–2025
  games; winner is the sign of the margin. Elo moves by K=60 x (result - expected). Conference title
  games are between the top two teams by conference record (ties broken by Elo, a simplification).
  Backtest Brier score: 0.020 (simulation) vs 0.028 (yes/no) for the field, 0.012 vs 0.020 for byes.
- **No leakage.** A committee list labeled "week W" comes out after week W-1's games, so only those
  games are used; postseason games never are. A test checks this for every snapshot.
- **Rules are verified against reality.** `tests/test_field.py` checks that the selection-rules code
  reproduces the real 2024 and 2025 playoff fields and seeds.
- **Source errors are corrected openly.** The data source lists the 2023 final ranking as "5, 5, 7"
  (no #6); the official list has Florida State #5, Georgia #6. The fix is a small documented table
  in `src/clean.py`.
- **Frozen model.** A test (`test_v1_feature_list_is_frozen`) fails if the Version 1 feature list is
  ever edited, so the scoreboard in section 4 always scores the model it claims to.

</details>

---

## How it works (the data pipeline)

Every Sunday (after Saturday's games) and Wednesday (after the committee's Tuesday list), a free
GitHub Actions job runs these steps in order and publishes the results to this page:

| Step | File | What it does |
|---|---|---|
| 1. Collect | `src/ingest.py` | Downloads games and rankings from the CollegeFootballData API |
| 2. Clean | `src/clean.py` | Keeps top-level games, drops and logs bad scores, one row per team per game |
| 3. Build résumés | `src/features.py` | Summarizes each team's season using only games already played |
| 4. Predict | `src/model.py`, `src/field.py` | Ranks teams, then applies the playoff selection rules |
| 5. Forecast | `src/forecast.py` | Predicts the committee's next list, saves it, scores earlier forecasts |
| 6. Simulate | `src/simulate.py` | Plays out the rest of the season for each team's odds |
| 7. Score | `src/scorecard.py` | Compares the locked model with each real committee list |
| 8. Explain | `src/explain.py` | Writes the plain-English "why" text in each section |
| 9. Check | `tests/` | 290+ automatic tests; the run stops and opens an issue if anything is wrong |

A second daily job watches for a silent failure (the weekly job never running) and opens an issue.

---

## Honest limitations

- **Early-season predictions are rough.** The model learned from committee lists, which start in
  November. Until the conference title games are played, each "champion" is just the current leader.
- **2026 seeding is an assumption.** The August 2026 rule announcement didn't say how seeds are assigned,
  so seeds here follow the ranking, as in 2025. The new 2026 automatic-spot rule has no real results
  to test against yet.
- **Small sample.** Eight test seasons isn't many, so small differences between model versions are noise.
- **Some things can't be measured here:** injuries, quarterback changes, and the committee's own judgment calls.
- **The odds assume the model's ranking is what the committee will do.** In reality the committee has
  its own surprises, so odds in the middle ranges are rougher than they look.

---

## Run it yourself

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env        # paste your free key from collegefootballdata.com
python -m src.ingest --years 2014-2026
python -m src.clean --years 2014-2026
python -m src.features --years 2014-2026
python -m src.model predict           # current field -> data/results/
python -m src.forecast                # next committee list + scoring
python -m src.simulate --sims 500     # odds for each team
python -m src.scorecard               # model vs. real committee lists
python -m src.model backtest          # how accurate is the model historically?
python -m pytest                      # run all tests
```

Weekly forecasts are saved in `data/results/forecasts/` and weekly predictions in
`data/results/history/`, so every past prediction can be checked later.

Data: [CollegeFootballData.com](https://collegefootballdata.com). The original exploratory analysis
that started this project is in `footballthing.Rmd`.
