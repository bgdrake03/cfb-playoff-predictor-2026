"""Tests for src/explain.py and for the README's auto-generated sections."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.explain import (
    advantages, compare_line, field_why, forecast_why, ordinal, plural, resume_line, scorecard_why, simulation_why, team_table,
)

README = Path(__file__).resolve().parent.parent / "README.md"


def team(name, wins=9, losses=1, sched=30, big=2, margin=15.0, rating=1900.0, last_rank=5.0, **kw):
    return {"team": name, "wins": wins, "losses": losses, "sos_now": 2000 - sched, "quality_wins_now": big,
            "avg_margin": margin, "elo_current": rating, "last_list_rank": last_rank, **kw}


def snapshot(rows) -> pd.DataFrame:
    return pd.DataFrame(rows)


def games(rows) -> pd.DataFrame:
    base = {"season_type": "regular", "week": 1, "start_date": "2026-09-01", "is_home": True, "neutral_site": False,
            "points_for": 30, "points_against": 20, "result": 1}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_ordinals_and_plurals():
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 101, 112)] == ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "101st", "112th"]
    assert plural(1, "win") == "1 win" and plural(3, "win") == "3 wins" and plural(0, "win") == "0 wins"


def test_team_table_ranks_schedule_and_finds_best_win_and_last_game():
    snap = snapshot([team("A", sched=1), team("B", sched=2), team("C", sched=3, rating=1500.0, last_rank=40.0)])
    g = games([
        {"team": "A", "opponent": "B", "week": 1}, {"team": "A", "opponent": "C", "week": 2, "result": 0, "points_for": 10, "points_against": 17, "is_home": False},
        {"team": "B", "opponent": "A", "week": 1, "result": 0}, {"team": "C", "opponent": "A", "week": 2},
    ])
    t = team_table(snap, g)
    assert t.loc["A", "schedule_rank"] == 1 and t.loc["C", "schedule_rank"] == 3  # 1 = hardest
    assert t.loc["A", "best_win"] == "B" and t.loc["A", "worst_loss"] == "C"
    assert t.loc["A", "last_game"] == "lost 10-17 at C"
    assert t.loc["A", "record"] == "9-1"


def test_last_game_shows_a_ranked_opponents_rank():
    snap = snapshot([team("A", last_rank=9.0), team("B", last_rank=2.0)])
    t = team_table(snap, games([{"team": "A", "opponent": "B", "result": 0, "points_for": 3, "points_against": 40, "is_home": True}]))
    assert t.loc["A", "last_game"] == "lost 3-40 vs #2 B"


def test_advantages_need_a_real_gap_and_show_at_most_two():
    a = pd.Series({"losses": 1, "schedule_rank": 5, "big_wins": 4, "avg_margin": 20.0, "elo_current": 2000.0})
    b = pd.Series({"losses": 3, "schedule_rank": 50, "big_wins": 1, "avg_margin": 10.0, "elo_current": 1800.0})
    assert len(advantages(a, b)) == 2
    same = pd.Series({"losses": 2, "schedule_rank": 30, "big_wins": 2, "avg_margin": 12.0, "elo_current": 1900.0})
    close = same.copy()
    close["elo_current"] = 1920.0
    assert advantages(same, close) == []  # a 20-point rating gap is not a real difference


def test_compare_line_names_both_teams_and_handles_a_dead_heat():
    snap = snapshot([team("In"), team("Out")])
    t = team_table(snap, games([{"team": "In", "opponent": "Out"}, {"team": "Out", "opponent": "In", "result": 0}]))
    line = compare_line("In", "Out", t)
    assert "last team in" in line and "first team out" in line and "coin flip" in line


def test_resume_line_is_plain_english():
    snap = snapshot([team("A", wins=10, losses=0, sched=5, big=1)])
    t = team_table(snap, games([{"team": "A", "opponent": "A"}]))
    line = resume_line(t.loc["A"])
    assert "10-0" in line and "hardest schedule of 1" in line and "1 big win" in line


def test_field_why_explains_automatic_spots_and_the_cut_line():
    snap = snapshot([team("Champ", sched=60), team("Good", sched=5), team("Next", sched=40, losses=3)])
    t = team_table(snap, games([{"team": "Champ", "opponent": "Good"}]))
    field = pd.DataFrame({"seed": [1, 2], "team": ["Champ", "Good"], "conference": ["X", "Y"], "record": ["9-1", "9-1"],
                          "reason": ["X champion", "at-large"], "rank": [30.0, 2.0]})
    ranking = pd.DataFrame({"predicted_seed": [2, 3, 30], "team": ["Good", "Next", "Champ"]})
    text = field_why(field, ranking, t)
    assert "Automatic spots" in text and "Champ (X champion)" in text
    assert "ranked 30th" in text  # a low-ranked champion is called out
    assert "last team in" in text and "Next" in text
    assert "<details>" in text and "</details>" in text


def test_notre_dame_style_reason_is_not_repeated():
    snap = snapshot([team("Notre Dame")])
    t = team_table(snap, games([{"team": "Notre Dame", "opponent": "Notre Dame"}]))
    field = pd.DataFrame({"seed": [1], "team": ["Notre Dame"], "conference": ["Ind"], "record": ["9-1"],
                          "reason": ["Notre Dame (ranked top 12)"], "rank": [5.0]})
    text = field_why(field, pd.DataFrame({"predicted_seed": [], "team": []}), t)
    assert "Notre Dame (Notre Dame" not in text


def sim_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "team": ["Lock", "Bubble", "LongShot"], "record": ["10-0", "8-3", "7-4"], "games_left": [1, 1, 1],
        "p_field": [1.0, 0.55, 0.05], "p_conf_champion": [0.5, 0.1, 0.6],
        "p_field_if_win_out": [1.0, 0.8, 0.1], "p_field_if_loses": [1.0, 0.05, 0.0],
    })


def test_simulation_why_covers_locks_bubble_and_long_shots():
    text = simulation_why(sim_frame())
    assert "Nearly locked in" in text and "Lock" in text
    assert "Bubble" in text and "80% if they win out" in text and "5% if they lose" in text
    assert "LongShot" in text and "Long shots" in text


def test_simulation_why_skips_missing_conditional_odds():
    df = sim_frame()
    df["p_field_if_win_out"] = np.nan
    assert "Bubble" not in simulation_why(df).split("Long shots")[0]


def test_scorecard_why_reports_stickiness_and_each_disagreement():
    rows = []
    for i in range(1, 15):
        rows.append(team(f"T{i}", last_rank=float(i)) | {"committee_rank": float(i) if i <= 12 else np.nan})
    w = snapshot(rows)
    score = pd.Series([14 - i for i in range(14)], index=w.index, dtype=float)  # model order = T1..T14
    score.loc[w["team"] == "T12"] = -50.0  # the model drops T12 out of its top 12
    t = team_table(w, games([{"team": "T1", "opponent": "T2"}]))
    text = scorecard_why(w, score, t, week=12)
    assert "barely re-ranks" in text and "didn't move at all" in text
    assert "T12" in text  # missed by the model
    assert "T13" in text  # model has them in instead


def test_forecast_why_lists_big_movers_with_their_last_result():
    snap = snapshot([team("Riser", last_rank=10.0), team("Steady", last_rank=1.0)])
    t = team_table(snap, games([{"team": "Riser", "opponent": "Steady", "points_for": 40, "points_against": 3},
                                {"team": "Steady", "opponent": "Riser", "result": 0, "points_for": 3, "points_against": 40}]))
    f = pd.DataFrame({"predicted_rank": [1, 2], "team": ["Steady", "Riser"], "last_list_rank": [1.0, 10.0]})
    f2 = pd.DataFrame({"predicted_rank": [1, 2], "team": ["Riser", "Steady"], "last_list_rank": [10.0, 1.0]})
    text = forecast_why(f2, t)
    assert "Riser" in text and "up" in text and "won 40-3" in text
    assert "exact same spot" in forecast_why(f, t)


# ---------- the README itself ----------

@pytest.mark.skipif(not README.exists(), reason="README missing")
def test_readme_keeps_every_generated_section_with_a_why():
    text = README.read_text(encoding="utf-8")
    for name in ("PREDICTION", "FORECAST", "SIMULATION", "SCORECARD"):
        start, end = f"<!-- {name}:START -->", f"<!-- {name}:END -->"
        assert text.count(start) == 1 and text.count(end) == 1, name
        block = text.split(start)[1].split(end)[0]
        assert block.strip(), f"{name} section is empty; run the pipeline"
        if "Waiting for new games" not in block and "has not released" not in block:
            assert "Why" in block or "depend on" in block, f"{name} section has no explanation"


@pytest.mark.skipif(not README.exists(), reason="README missing")
def test_readme_explains_football_terms_for_newcomers():
    text = README.read_text(encoding="utf-8").lower()
    for term in ("the committee", "seed", "conference", "automatic spot", "schedule strength", "bubble"):
        assert term in text, f"glossary is missing: {term}"
