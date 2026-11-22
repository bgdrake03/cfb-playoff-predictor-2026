"""Tests for the scoring helpers in src/simulate_backtest.py."""
import pandas as pd
import pytest

from src.simulate_backtest import brier, calibration


def test_brier_perfect_worst_and_coin_flip():
    outcome = pd.Series([1, 0, 1, 0])
    assert brier(outcome.astype(float), outcome) == 0
    assert brier(1 - outcome.astype(float), outcome) == 1
    assert brier(pd.Series([0.5] * 4), outcome) == pytest.approx(0.25)


def test_calibration_groups_by_probability_bucket():
    df = pd.DataFrame({"p": [0.01, 0.02, 0.5, 0.52, 0.99, 0.97], "hit": [0, 0, 1, 0, 1, 1]})
    table = calibration(df, "p", "hit")
    assert table["team_seasons"].sum() == 6
    assert table.loc[table["predicted"] > 0.9, "actual"].iloc[0] == 1.0
    assert table.loc[table["predicted"] < 0.1, "actual"].iloc[0] == 0.0
