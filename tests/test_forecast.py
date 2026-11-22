"""Tests for src/forecast.py (the weekly next-list forecast, model v3)."""
import numpy as np
import pandas as pd
import pytest

from src.forecast import END, START, actual_top12, make_forecast, render_block, repeat_last_list, summarize_backtest
from src.model import FEATURES, FEATURES_V3


def week_frame() -> pd.DataFrame:
    teams = [f"T{i}" for i in range(14)]
    return pd.DataFrame({
        "team": teams,
        "last_list_rank": list(range(1, 13)) + [13.0, 40.0],
        "committee_rank": [2, 1] + list(range(3, 13)) + [np.nan, np.nan],
    })


def test_repeat_last_list_is_the_previous_top_12_in_order():
    teams = repeat_last_list(week_frame())
    assert teams == [f"T{i}" for i in range(12)]


def test_actual_top12_orders_by_committee_rank():
    top = actual_top12(week_frame())
    assert top[:2] == ["T1", "T0"] and len(top) == 12


def test_v3_adds_only_the_last_list_to_v1():
    assert FEATURES_V3 == FEATURES + ["last_list_rank"]


def test_no_forecast_when_the_newest_list_is_already_published():
    df = pd.DataFrame({"season_complete": [0] * 3, "ranking_week": [12] * 3, "committee_rank": [1.0, 2.0, 3.0],
                       "last_list_rank": [1.0, 2.0, 3.0]})
    assert make_forecast(df) is None


def test_no_forecast_before_any_committee_list_exists():
    df = pd.DataFrame({"season_complete": [0] * 3, "ranking_week": [9] * 3, "committee_rank": [np.nan] * 3,
                       "last_list_rank": [np.nan] * 3})
    assert make_forecast(df) is None


def test_summary_counts_better_same_worse():
    rows = []
    for i, (v1, v3, rep) in enumerate([(10, 11, 10), (11, 11, 10), (12, 11, 11)]):
        for name, val in (("model_v1", v1), ("v3_forecast", v3), ("repeat_last_list", rep)):
            rows.append({"season": 2020, "list_week": i, "method": name, "top12_correct": val, "seed_error": 1.0})
    s = summarize_backtest(pd.DataFrame(rows))
    assert (s["better"], s["same"], s["worse"], s["lists"]) == (1, 1, 1, 3)


def test_readme_block_has_markers_and_handles_no_scores_yet():
    forecast = pd.DataFrame({"predicted_rank": [1], "team": ["Georgia"], "conference": ["SEC"], "record": ["9-1"],
                             "last_list_rank": [1.0], "score": [0.9]})
    block = render_block(13, forecast, pd.DataFrame(), None)
    assert block.startswith(START) and block.endswith(END)
    assert "Georgia" in block and "None yet" in block


def test_readme_block_when_waiting_for_games():
    assert "Waiting for new games" in render_block(None, None, pd.DataFrame(), None)
