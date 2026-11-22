"""Tests for src/simulate.py: the probabilities must obey the invariants of the sport."""
import numpy as np
import pytest

from src import simulate as S

try:
    CTX = S.Context()
except Exception:  # features/clean data not built yet
    CTX = None

needs_data = pytest.mark.skipif(CTX is None, reason="Run the pipeline first")


def test_win_probability_is_symmetric_and_monotonic():
    m = np.array([-30.0, -10.0, 0.0, 10.0, 30.0])
    p = S.win_prob(m)
    assert p[2] == pytest.approx(0.5)
    assert np.allclose(p + p[::-1], 1.0)
    assert (np.diff(p) > 0).all()


def test_fitted_game_model_matches_observed_win_rates():
    # A 10-point favourite should win about 73%, a 3-point (home-field) edge about 57-58%.
    assert S.win_prob(np.array([10.0]))[0] == pytest.approx(0.73, abs=0.03)
    assert S.win_prob(np.array([S.HOME_MARGIN]))[0] == pytest.approx(0.58, abs=0.02)


@needs_data
def test_schedule_excludes_postseason_and_games_after_selection_day():
    up = CTX.upcoming
    assert (up["seasonType"] == "regular").all()
    assert (up["startDate"].str[:10] < S.SELECTION_DATE).all()


@needs_data
def test_probabilities_obey_the_rules_of_the_field():
    result = S.run(n_sims=12, seed=1)
    assert result["p_field"].between(0, 1).all() and result["p_bye"].between(0, 1).all()
    assert result["p_field"].sum() == pytest.approx(12.0)  # exactly 12 spots every simulation
    assert result["p_bye"].sum() == pytest.approx(4.0)  # exactly 4 byes every simulation
    assert (result["p_bye"] <= result["p_field"] + 1e-9).all()
    assert result["p_conf_champion"].sum() == pytest.approx(10.0)  # one champion per conference


@needs_data
def test_same_seed_gives_identical_results():
    a = S.run(n_sims=6, seed=7)
    b = S.run(n_sims=6, seed=7)
    assert a.equals(b)
