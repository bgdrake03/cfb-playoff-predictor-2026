"""Backtest the season simulator: are its probabilities trustworthy?

For each past season we rewind to two committee weeks before Selection Day (the same position
we are in now), using only games already played then and a model trained only on EARLIER
seasons. We simulate the rest of the season, then compare each team's simulated probability of
making the field with whether it actually made it.

"Actually made it" = the 2026 selection rules applied to the committee's real final ranking and
the real conference champions (a what-if for years before the rules existed, applied the same
way to prediction and truth, so the comparison is fair).

Usage:
    python -m src.simulate_backtest --sims 200
"""
import argparse
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from src.field import select_field
from src.model import FEATURES, RESULT_DIR, as_ranked_table, load_features
from src.simulate import Context, run

# 2019 and 2020 are skipped: their week numbering doesn't follow the usual pattern.
TEST_SEASONS = [2017, 2018, 2021, 2022, 2023, 2024, 2025]
WEEKS_BEFORE_SELECTION = 2
BINS = [0, 0.05, 0.2, 0.4, 0.6, 0.8, 0.95, 1.0]


def actual_field(season_df: pd.DataFrame) -> pd.DataFrame:
    final = season_df[season_df["ranking_week"] == season_df["ranking_week"].max()]
    return select_field(as_ranked_table(final, final["committee_rank"]), "2026")


def one_season(args: tuple[int, int, int]) -> pd.DataFrame:
    year, n_sims, seed = args
    df = load_features()
    season = df[df["season"] == year]
    as_of = int(season["ranking_week"].max()) - WEEKS_BEFORE_SELECTION
    ctx = Context(year=year, as_of_week=as_of, train_before=year)

    sim = run(n_sims, seed, ctx)
    truth = actual_field(season)
    sim["actual_in"] = sim["team"].isin(truth["team"]).astype(int)
    sim["actual_bye"] = sim["team"].isin(truth.loc[truth["seed"] <= 4, "team"]).astype(int)

    # The no-simulation alternative: model ranking of today's standings, as a 0/1 prediction.
    snap = ctx.snapshot_df.copy()
    rank = pd.Series(ctx.model.predict(snap[FEATURES]), index=snap.index).rank(ascending=False, method="first")
    point = select_field(as_ranked_table(snap, rank), "2026")
    sim["point_in"] = sim["team"].isin(point["team"]).astype(int)
    sim["point_bye"] = sim["team"].isin(point.loc[point["seed"] <= 4, "team"]).astype(int)
    sim["season"] = year
    sim["as_of_week"] = as_of
    return sim


def calibration(results: pd.DataFrame, prob: str, actual: str) -> pd.DataFrame:
    binned = pd.cut(results[prob], BINS, include_lowest=True)
    table = results.groupby(binned, observed=True).agg(
        team_seasons=(actual, "size"), predicted=(prob, "mean"), actual=(actual, "mean")
    )
    return table.round(3)


def brier(p: pd.Series, outcome: pd.Series) -> float:
    return float(((p - outcome) ** 2).mean())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sims", type=int, default=200)
    args = parser.parse_args()

    with ProcessPoolExecutor() as pool:
        frames = list(pool.map(one_season, [(y, args.sims, 100 + y) for y in TEST_SEASONS]))
    results = pd.concat(frames, ignore_index=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    results.to_csv(RESULT_DIR / "simulation_backtest.csv", index=False)

    print(f"Rewound to {WEEKS_BEFORE_SELECTION} committee weeks before Selection Day; {args.sims} simulations per season.")
    print(f"Seasons: {TEST_SEASONS}\n")
    print("MAKES THE FIELD: predicted probability vs how often it actually happened")
    print(calibration(results, "p_field", "actual_in").to_string())
    print("\nFIRST-ROUND BYE:")
    print(calibration(results, "p_bye", "actual_bye").to_string())

    print("\nBrier score (lower is better; 0 = perfect, 0.25 = always guessing 50%):")
    rows = {
        "simulation (probabilities)": (brier(results["p_field"], results["actual_in"]), brier(results["p_bye"], results["actual_bye"])),
        "no simulation (yes/no)": (brier(results["point_in"], results["actual_in"]), brier(results["point_bye"], results["actual_bye"])),
    }
    print(pd.DataFrame(rows, index=["field", "bye"]).T.round(4).to_string())

    print("\nPer season: how many of the 12 actual teams had a simulated chance above 50%?")
    for year, g in results.groupby("season"):
        hit = int(((g["p_field"] > 0.5) & (g["actual_in"] == 1)).sum())
        print(f"  {year}: {hit}/12 had >50%   (sum of probabilities for the real 12 = {g.loc[g['actual_in'] == 1, 'p_field'].sum():.1f})")


if __name__ == "__main__":
    main()
