"""Tests for the scoring helpers and model plumbing in src/model.py."""
import numpy as np
import pandas as pd

from src.model import FEATURES, Blend, add_target, make_models, score_prediction, top_field


def test_perfect_prediction_scores_full_marks():
    teams = [f"T{i}" for i in range(12)]
    s = score_prediction(teams, teams)
    assert (s["top12_correct"], s["top4_correct"], s["seed_error"]) == (12, 4, 0)


def test_one_wrong_team_and_seed_error():
    actual = [f"T{i}" for i in range(12)]
    predicted = actual[:11] + ["Outsider"]
    s = score_prediction(predicted, actual)
    assert s["top12_correct"] == 11 and s["seed_error"] == 0

    swapped = [actual[1], actual[0]] + actual[2:]
    assert score_prediction(swapped, actual)["seed_error"] == 2 / 12


def test_target_is_25_for_first_and_zero_for_unranked():
    df = pd.DataFrame({"committee_rank": [1.0, 25.0, np.nan]})
    assert add_target(df)["target"].tolist() == [25, 1, 0]


def test_top_field_orders_by_score_then_elo():
    week = pd.DataFrame({"team": ["A", "B", "C"], "elo_current": [1500, 1600, 1400]})
    assert top_field(week, pd.Series([1.0, 1.0, 5.0]), n=3) == ["C", "B", "A"]


def test_no_team_names_or_human_polls_used_as_inputs():
    banned = {"team", "conference"}
    assert not banned & set(FEATURES)
    assert not any(f.startswith("ref_") for f in FEATURES)


def test_every_model_trains_and_scores_without_error():
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.normal(size=(200, 3)), columns=["a", "b", "c"])
    y = pd.Series((X["a"] * 5 + 13).clip(0, 25))
    for name, model in make_models().items():
        scores = model.fit(X, y).predict(X)
        assert len(scores) == 200, name
        assert np.corrcoef(scores, X["a"])[0, 1] > 0.5, name


def test_blend_is_average_of_standardized_scores():
    class Const:
        def __init__(self, v): self.v = np.array(v, dtype=float)
        def fit(self, X, y): return self
        def predict(self, X): return self.v

    blend = Blend([Const([1, 2, 3]), Const([10, 20, 30])])
    out = blend.predict(None)
    assert np.allclose(out, [-1.2247, 0, 1.2247], atol=1e-3)


def test_v1_feature_list_is_frozen():
    """model-v1 was frozen on 2026-10-17. If this fails, the live scorecard no longer scores the
    model it claims to. Create a new model version instead of editing this list."""
    from src.model import FEATURES

    assert FEATURES == [
        "wins", "losses", "win_pct", "fbs_wins", "fbs_losses", "avg_margin", "sos",
        "quality_wins", "quality_losses", "bad_losses", "best_win_elo", "worst_loss_elo",
        "last3_wins", "elo_current", "undefeated",
        "sos_now", "quality_wins_now", "bad_losses_now", "win_value", "loss_cost",
        "best_win_now", "worst_loss_now",
    ]


def test_v2_only_adds_conference_strength():
    from src.model import CONF_STRENGTH_FEATURES, FEATURES, FEATURES_V2

    assert FEATURES_V2 == FEATURES + CONF_STRENGTH_FEATURES
