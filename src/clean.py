"""Clean the raw CFBD downloads into analysis-ready tables.

Reads  data/raw/games_<year>.csv and rankings_<year>.csv
Writes data/clean/team_games_<year>.csv   one row per FBS team per completed game
       data/clean/upcoming_<year>.csv     FBS games not yet played
       data/clean/rankings_<year>.csv     AP, Coaches and CFP Committee polls only
       data/clean/dropped_games_<year>.csv  every game removed for bad data, with a reason

Usage:
    python -m src.clean            # defaults to 2026
    python -m src.clean --year 2025
    python -m src.clean --years 2014-2025
"""
import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
CLEAN_DIR = ROOT / "data" / "clean"

# Known errors in the CFBD source, each verified against the official CFP release.
# (season, poll, seasonType, week, school) -> correct rank
RANK_CORRECTIONS = {
    # Dec 3 2023 final list: FSU #5, Georgia #6. CFBD lists both at 5 and skips 6.
    (2023, "Playoff Committee Rankings", "regular", 15, "Georgia"): 6,
}

POLLS_KEPT = ["AP Top 25", "Coaches Poll", "Playoff Committee Rankings"]


def flag_bad_scores(games: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split off completed games whose score is missing or impossible.

    Returns (good_games, dropped_games). Dropped games get a `drop_reason` column.
    This runs on ALL divisions so nothing is silently discarded.
    """
    completed = games["completed"].astype(bool)
    missing = games["homePoints"].isna() | games["awayPoints"].isna()
    negative = (games["homePoints"] < 0) | (games["awayPoints"] < 0)

    reason = pd.Series(pd.NA, index=games.index, dtype="object")
    reason[completed & missing] = "completed_but_missing_score"
    reason[completed & ~missing & negative] = "negative_score"

    bad = reason.notna()
    dropped = games[bad].assign(drop_reason=reason[bad])
    return games[~bad].copy(), dropped


def keep_fbs_games(games: pd.DataFrame) -> pd.DataFrame:
    """Keep games where at least one team is FBS (FBS vs FCS games stay, flagged later)."""
    is_fbs = (games["homeClassification"] == "fbs") | (games["awayClassification"] == "fbs")
    return games[is_fbs].copy()


def to_team_games(games: pd.DataFrame) -> pd.DataFrame:
    """Reshape one-row-per-game into one-row-per-team-per-game, FBS teams only."""

    def side(me: str, opp: str, is_home: bool) -> pd.DataFrame:
        df = pd.DataFrame(
            {
                "game_id": games["id"],
                "season": games["season"],
                "season_type": games["seasonType"],
                "week": games["week"],
                "start_date": games["startDate"],
                "team": games[f"{me}Team"],
                "team_conference": games[f"{me}Conference"],
                "team_classification": games[f"{me}Classification"],
                "opponent": games[f"{opp}Team"],
                "opponent_conference": games[f"{opp}Conference"],
                "opponent_classification": games[f"{opp}Classification"],
                "is_home": is_home,
                "neutral_site": games["neutralSite"],
                "conference_game": games["conferenceGame"],
                "points_for": games[f"{me}Points"],
                "points_against": games[f"{opp}Points"],
                "team_pregame_elo": games[f"{me}PregameElo"],
                "opponent_pregame_elo": games[f"{opp}PregameElo"],
                "team_postgame_elo": games[f"{me}PostgameElo"],
            }
        )
        return df

    rows = pd.concat(
        [side("home", "away", True), side("away", "home", False)], ignore_index=True
    )
    rows = rows[rows["team_classification"] == "fbs"].copy()

    # Missing classification means a small school we don't track: treat as non-FBS.
    rows["opponent_is_fbs"] = rows["opponent_classification"] == "fbs"
    rows["is_home"] = rows["is_home"] & ~rows["neutral_site"].astype(bool)
    rows["margin"] = rows["points_for"] - rows["points_against"]
    rows["result"] = (rows["margin"] > 0).astype(int)
    rows["week"] = rows["week"].astype(int)
    return rows.sort_values(["team", "week", "game_id"]).reset_index(drop=True)


def clean_rankings(rankings: pd.DataFrame) -> pd.DataFrame:
    out = rankings[rankings["poll"].isin(POLLS_KEPT)].copy()
    out = out.dropna(subset=["rank", "school"])
    for (season, poll, season_type, week, school), rank in RANK_CORRECTIONS.items():
        hit = (
            (out["season"] == season) & (out["poll"] == poll) & (out["seasonType"] == season_type)
            & (out["week"] == week) & (out["school"] == school)
        )
        out.loc[hit, "rank"] = rank
    out["rank"] = out["rank"].astype(int)
    out["week"] = out["week"].astype(int)
    return out.sort_values(["poll", "week", "rank"]).reset_index(drop=True)


def clean(year: int) -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    games = pd.read_csv(RAW_DIR / f"games_{year}.csv")
    rankings = pd.read_csv(RAW_DIR / f"rankings_{year}.csv")
    print(f"Raw: {len(games)} games, {len(rankings)} ranking rows")

    games = games.drop_duplicates(subset="id")

    good, dropped = flag_bad_scores(games)
    dropped.to_csv(CLEAN_DIR / f"dropped_games_{year}.csv", index=False)
    if len(dropped):
        print(f"WARNING: dropped {len(dropped)} game(s) with bad scores:")
        for _, g in dropped.iterrows():
            print(f"  week {g['week']}: {g['homeTeam']} vs {g['awayTeam']} ({g['drop_reason']})")

    fbs = keep_fbs_games(good)
    print(f"Kept {len(fbs)} games involving an FBS team (removed {len(good) - len(fbs)} others)")

    played = fbs[fbs["completed"].astype(bool)]
    upcoming = fbs[~fbs["completed"].astype(bool)]

    team_games = to_team_games(played)
    team_games.to_csv(CLEAN_DIR / f"team_games_{year}.csv", index=False)
    print(f"Wrote {len(team_games)} team-game rows ({played['id'].nunique()} completed games)")

    upcoming_cols = [
        "id", "seasonType", "week", "startDate", "homeTeam", "awayTeam", "neutralSite", "conferenceGame",
        "homeConference", "awayConference", "homeClassification", "awayClassification",
    ]
    upcoming[upcoming_cols].to_csv(CLEAN_DIR / f"upcoming_{year}.csv", index=False)
    print(f"Wrote {len(upcoming)} upcoming games")

    ranks = clean_rankings(rankings)
    ranks.to_csv(CLEAN_DIR / f"rankings_{year}.csv", index=False)
    print(f"Wrote {len(ranks)} ranking rows ({', '.join(POLLS_KEPT)})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--years", help="Inclusive range such as 2014-2025; overrides --year")
    args = parser.parse_args()
    if args.years:
        first, last = (int(y) for y in args.years.split("-"))
        for y in range(first, last + 1):
            print(f"--- {y} ---")
            clean(y)
    else:
        clean(args.year)
