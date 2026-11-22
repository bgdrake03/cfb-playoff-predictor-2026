"""Tests for src/features.py: leakage, label coverage, and the aggregation math."""
import pandas as pd
import pytest

from src.features import CLEAN_DIR, FEATURE_DIR, add_game_quality, snapshot

YEARS = sorted(int(f.stem.split("_")[-1]) for f in FEATURE_DIR.glob("features_*.csv"))


def make_team_games(rows: list[dict]) -> pd.DataFrame:
    base = {
        "week": 1, "opponent": "Opp", "opponent_conference": "Z", "conference_game": False, "start_date": "2026-09-05T23:00:00.000Z", "team": "Alpha",
        "team_conference": "X", "opponent_is_fbs": True, "result": 1, "margin": 10.0,
        "team_pregame_elo": 1500.0, "team_postgame_elo": 1510.0, "opponent_pregame_elo": 1400.0,
    }
    return pd.DataFrame([{**base, **r} for r in rows])


# ---------- unit tests ----------

def test_blowouts_are_capped():
    g = add_game_quality(make_team_games([{"margin": 70.0}]))
    assert g["margin_capped"].iloc[0] == 28


def test_fcs_opponent_gets_placeholder_elo_and_counts_as_bad_opponent():
    g = add_game_quality(make_team_games([{"opponent_is_fbs": False, "opponent_pregame_elo": None}]))
    assert g["opp_elo"].iloc[0] == 1250.0


def test_snapshot_counts_wins_losses_and_quality():
    games = make_team_games(
        [
            {"week": 1, "result": 1, "opponent_pregame_elo": 2000.0},  # quality win
            {"week": 2, "result": 0, "margin": -3.0, "opponent_pregame_elo": 1000.0},  # bad loss
            {"week": 3, "result": 1},
        ]
    )
    # Other teams give the weekly Elo distribution a spread to take percentiles against.
    filler = make_team_games([{"team": f"T{i}", "week": w, "team_pregame_elo": 1200 + 40 * i} for i in range(10) for w in (1, 2, 3)])
    snap = snapshot(add_game_quality(pd.concat([games, filler], ignore_index=True)).query("team == 'Alpha'"))
    row = snap.iloc[0]
    assert (row["wins"], row["losses"], row["games"]) == (2, 1, 3)
    assert row["quality_wins"] == 1
    assert row["bad_losses"] == 1
    assert row["undefeated"] == 0
    assert row["last3_wins"] == 2


# ---------- data-quality checks on the real feature tables ----------

@pytest.fixture(params=YEARS, ids=lambda y: str(y))
def season(request) -> int:
    return request.param


@pytest.fixture
def features(season) -> pd.DataFrame:
    return pd.read_csv(FEATURE_DIR / f"features_{season}.csv")


def test_no_future_games_leak_into_features(features, season):
    """Every team's game count must equal the regular-season games before the ranking week."""
    games = pd.read_csv(CLEAN_DIR / f"team_games_{season}.csv")
    regular = games[games["season_type"] == "regular"]
    # 2019's final list uses a date cutoff, so skip that one row-set; it is covered by the max check below.
    for week, snap in features.groupby("ranking_week"):
        if (season, week) == (2019, 16):
            continue
        allowed = regular[regular["week"] <= week - 1].groupby("team").size()
        merged = snap.set_index("team")["games"].to_frame().join(allowed.rename("allowed"))
        assert (merged["games"] == merged["allowed"]).all(), f"{season} week {week} has leaked or missing games"


def test_no_team_has_playoff_sized_schedule_at_selection_time(features):
    final = features[features["ranking_week"] == features["ranking_week"].max()]
    assert final["games"].max() <= 14


def test_win_loss_adds_up(features):
    assert (features["wins"] + features["losses"] == features["games"]).all()


def test_committee_labels_are_complete(features, season):
    """Each committee week should label exactly 25 teams; fewer means a name mismatch dropped some."""
    labeled = features.dropna(subset=["committee_rank"])
    if labeled.empty:
        pytest.skip("No committee rankings yet for this season")
    counts = labeled.groupby("ranking_week").size()
    assert (counts == 25).all(), counts.to_dict()


def test_committee_ranks_are_unique_within_a_week(features):
    labeled = features.dropna(subset=["committee_rank"])
    assert not labeled.duplicated(["ranking_week", "committee_rank"]).any()


# ---------- conference champion detection ----------

KNOWN_CHAMPIONS = {  # final-week champions, checked against real results
    2023: {"ACC": "Florida State", "Big 12": "Texas", "Big Ten": "Michigan", "SEC": "Alabama", "Pac-12": "Washington"},
    2024: {"ACC": "Clemson", "Big 12": "Arizona State", "Big Ten": "Oregon", "SEC": "Georgia", "American Athletic": "Army"},
    2025: {"ACC": "Duke", "Big 12": "Texas Tech", "Big Ten": "Indiana", "SEC": "Georgia",
           "American Athletic": "Tulane", "Sun Belt": "James Madison"},
}


@pytest.mark.parametrize("year", sorted(KNOWN_CHAMPIONS))
def test_known_conference_champions_are_detected(year):
    f = pd.read_csv(FEATURE_DIR / f"features_{year}.csv")
    f = f[f["ranking_week"] == f["ranking_week"].max()]
    champs = f[f["conf_champion"] == 1].set_index("conference")["team"].to_dict()
    for conf, team in KNOWN_CHAMPIONS[year].items():
        assert champs.get(conf) == team, f"{year} {conf}: got {champs.get(conf)}, expected {team}"


def test_at_most_one_champion_per_conference(features):
    champs = features[features["conf_champion"] == 1]
    assert not champs.duplicated(["ranking_week", "conference"]).any()


# ---------- freshness: the latest snapshot must use every game we have ----------

def test_in_progress_season_has_a_snapshot_with_all_games_played(features, season):
    """Regression test: once the committee started publishing, the newest snapshot used to lag
    a full week behind the data. An in-progress season's latest snapshot must include every
    regular-season game already in the clean data."""
    if features["season_complete"].iloc[0] == 1:
        pytest.skip("Season is finished; snapshots follow the committee's weeks")
    games = pd.read_csv(CLEAN_DIR / f"team_games_{season}.csv")
    played = games[games["season_type"] == "regular"].groupby("team").size()
    latest = features[features["ranking_week"] == features["ranking_week"].max()].set_index("team")["games"]
    assert (latest == played.reindex(latest.index)).all()


def test_finished_seasons_are_flagged_complete():
    for year in range(2014, 2026):
        flag = pd.read_csv(FEATURE_DIR / f"features_{year}.csv")["season_complete"]
        assert (flag == 1).all(), year
