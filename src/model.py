"""Predict the College Football Playoff committee's top 12 and test how well that works.

Two commands:
    python -m src.model backtest   # walk-forward test on past seasons -> data/results/
    python -m src.model predict    # rank the 2026 teams as of the latest week

How the test is honest: to predict season Y, the model trains ONLY on seasons before Y,
the way it would have to work in real life. We compare it with simple baselines, and
compare training on all prior seasons against only the most recent few.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from src.field import select_field
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
FEATURE_DIR = ROOT / "data" / "features"
RESULT_DIR = ROOT / "data" / "results"

# Resume features only. No team names, no human polls (ref_* columns are for baselines).
BASE_FEATURES = [
    "wins", "losses", "win_pct", "fbs_wins", "fbs_losses", "avg_margin", "sos",
    "quality_wins", "quality_losses", "bad_losses", "best_win_elo", "worst_loss_elo",
    "last3_wins", "elo_current", "undefeated",
]
# Opponents judged by their rating now (hindsight), the way a committee sees them.
HINDSIGHT_FEATURES = [
    "sos_now", "quality_wins_now", "bad_losses_now", "win_value", "loss_cost",
    "best_win_now", "worst_loss_now",
]
FEATURES = BASE_FEATURES + HINDSIGHT_FEATURES
# Built in features.py but NOT used: in testing, conference-record features did not improve
# predictions (10.75 vs 10.75 of 12). Better handled as the post-2024 auto-bid rule.
CONFERENCE_FEATURES = ["conf_win_pct", "conf_losses", "conf_leader"]

EXCLUDED_SEASONS = {2020}  # COVID season: schedules and committee weeks don't follow the usual pattern
FIRST_TEST_SEASON = 2017  # need at least 3 prior seasons to train on
RECENT_WINDOW = 3
FIELD_SIZE = 12
UNRANKED_SCORE = 0


def finished_seasons(df: pd.DataFrame) -> pd.DataFrame:
    """Seasons that are over (postseason played). An in-progress season has no Selection Day
    list yet, so it must never be used to train or to score the model."""
    return df[(df["season_complete"] == 1) & ~df["season"].isin(EXCLUDED_SEASONS)]


def load_features() -> pd.DataFrame:
    frames = [pd.read_csv(f) for f in sorted(FEATURE_DIR.glob("features_*.csv"))]
    return pd.concat(frames, ignore_index=True)


def add_target(df: pd.DataFrame) -> pd.DataFrame:
    """Committee score: 25 for #1 down to 1 for #25, 0 for unranked. Higher = better."""
    out = df.copy()
    out["target"] = (26 - out["committee_rank"]).fillna(UNRANKED_SCORE)
    return out


class TopTwelveClassifier(BaseEstimator, RegressorMixin):
    """Predict 'will the committee rank this team top 12?' and score teams by that probability."""

    def __init__(self, clf):
        self.clf = clf

    def fit(self, X, y):
        self.clf.fit(X, (y >= 26 - FIELD_SIZE).astype(int))
        return self

    def predict(self, X):
        return self.clf.predict_proba(X)[:, 1]


class Blend(BaseEstimator, RegressorMixin):
    """Average several models after putting their scores on the same scale."""

    def __init__(self, models):
        self.models = models

    def fit(self, X, y):
        for model in self.models:
            model.fit(X, y)
        return self

    def predict(self, X):
        def z(a):
            return (a - a.mean()) / (a.std() + 1e-9)

        return sum(z(model.predict(X)) for model in self.models) / len(self.models)


def _ridge():
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=10.0))


def _gbm():
    return make_pipeline(
        SimpleImputer(strategy="median"),
        GradientBoostingRegressor(n_estimators=150, max_depth=2, learning_rate=0.05, subsample=0.8, random_state=0),
    )


def _logit():
    return TopTwelveClassifier(
        make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(C=0.3, max_iter=1000))
    )


def make_models() -> dict:
    """Candidates compared in the backtest. 'blend' is the production model."""
    return {
        "blend": Blend([_ridge(), _gbm(), _logit()]),
        "ridge": _ridge(),
        "gbm": _gbm(),
        "logit": _logit(),
    }


# ---------- ranking from scores ----------

def top_field(week_df: pd.DataFrame, score: pd.Series, n: int = FIELD_SIZE) -> list[str]:
    """Teams ordered best-first by score (ties broken by Elo so results are deterministic)."""
    order = week_df.assign(_s=score.values).sort_values(["_s", "elo_current"], ascending=False)
    return order["team"].head(n).tolist()


def score_prediction(predicted: list[str], actual: list[str]) -> dict:
    """How close was a predicted ordered top-12 to the committee's?"""
    overlap = len(set(predicted) & set(actual))
    both = [t for t in predicted if t in actual]
    seed_err = np.mean([abs(predicted.index(t) - actual.index(t)) for t in both]) if both else np.nan
    return {
        "top12_correct": overlap,
        "top4_correct": len(set(predicted[:4]) & set(actual[:4])),
        "seed_error": seed_err,  # average seeds off, among teams we got into the field
    }


# ---------- baselines ----------

def baseline_scores(week_df: pd.DataFrame) -> dict[str, pd.Series]:
    ap = (26 - week_df["ref_ap_rank"]).fillna(0)
    elo = week_df["elo_current"]
    # Roughly the "record, then schedule" logic a fan would use: fewer losses first, then tougher schedule.
    record_sos = -week_df["losses"] * 10_000 + week_df["sos"]
    return {"ap_poll": ap, "elo_only": elo, "record_then_sos": record_sos}


# ---------- walk-forward backtest ----------

def backtest(df: pd.DataFrame, features: list[str] = None, make=None) -> pd.DataFrame:
    features = features or FEATURES
    make = make or make_models
    df = add_target(finished_seasons(df))
    labeled = df[df["committee_rank"].notna() | df.groupby(["season", "ranking_week"])["committee_rank"].transform(lambda s: s.notna().any())]
    seasons = sorted(labeled["season"].unique())
    rows = []

    for test_season in [s for s in seasons if s >= FIRST_TEST_SEASON]:
        prior = [s for s in seasons if s < test_season]
        windows = {"all_prior": prior, f"last{RECENT_WINDOW}": prior[-RECENT_WINDOW:]}
        test = labeled[labeled["season"] == test_season]

        fitted = {}
        for window_name, train_seasons in windows.items():
            train = labeled[labeled["season"].isin(train_seasons)]
            for model_name, model in make().items():
                fitted[f"{model_name}_{window_name}"] = model.fit(train[features], train["target"])

        final_week = test["ranking_week"].max()
        for week, week_df in test.groupby("ranking_week"):
            actual = week_df.dropna(subset=["committee_rank"]).sort_values("committee_rank")["team"].head(FIELD_SIZE).tolist()
            methods = {name: pd.Series(m.predict(week_df[features]), index=week_df.index) for name, m in fitted.items()}
            methods.update(baseline_scores(week_df))
            for name, score in methods.items():
                rows.append(
                    {"season": test_season, "ranking_week": week, "is_final_week": week == final_week,
                     "method": name, **score_prediction(top_field(week_df, score), actual)}
                )
    return pd.DataFrame(rows)


def summarize(results: pd.DataFrame) -> pd.DataFrame:
    final = results[results["is_final_week"]]
    summary = pd.DataFrame(
        {
            "final_week_top12": final.groupby("method")["top12_correct"].mean(),
            "final_week_top4": final.groupby("method")["top4_correct"].mean(),
            "final_week_seed_err": final.groupby("method")["seed_error"].mean(),
            "all_weeks_top12": results.groupby("method")["top12_correct"].mean(),
        }
    )
    return summary.sort_values("final_week_top12", ascending=False).round(2)



# ---------- playoff-field backtest (model + selection rules) ----------

FIELD_RULE_BY_SEASON = {2024: "2024", 2025: "2025"}  # real rules; earlier seasons use the 2026 rule as a what-if


def as_ranked_table(week_df: pd.DataFrame, rank: pd.Series) -> pd.DataFrame:
    return pd.DataFrame(
        {"team": week_df["team"], "conference": week_df["conference"],
         "conf_champion": week_df["conf_champion"], "rank": rank}
    )


def backtest_field(df: pd.DataFrame) -> pd.DataFrame:
    """Compare 'model top 12' with 'model ranking + selection rules' against the true field.

    The true field = the rules applied to the committee's own final ranking.
    Champions are known by Selection Day, so using them here is fair.
    """
    df = add_target(finished_seasons(df))
    seasons = sorted(df.loc[df["committee_rank"].notna(), "season"].unique())
    rows = []
    for test_season in [s for s in seasons if s >= FIRST_TEST_SEASON]:
        train = df[df["season"].isin([s for s in seasons if s < test_season])]
        model = make_models()["blend"].fit(train[FEATURES], train["target"])

        final = df[(df["season"] == test_season) & (df["ranking_week"] == df.loc[df["season"] == test_season, "ranking_week"].max())].copy()
        final["score"] = model.predict(final[FEATURES])
        model_rank = final["score"].rank(ascending=False, method="first")

        for rule in sorted({FIELD_RULE_BY_SEASON.get(test_season, "2026"), "2026"}):
            truth = select_field(as_ranked_table(final, final["committee_rank"]), rule)
            with_rules = select_field(as_ranked_table(final, model_rank), rule)
            plain = top_field(final, final["score"])  # model's top 12, ignoring the rules
            for name, teams in [("model_top12_only", plain), ("model_plus_rules", with_rules["team"].tolist())]:
                seeds = truth["team"].tolist()
                rows.append({"season": test_season, "rule": rule, "method": name,
                             "field_correct": len(set(teams) & set(seeds)), "byes_correct": len(set(teams[:4]) & set(seeds[:4]))})
    return pd.DataFrame(rows)

# ---------- predict the current season ----------

def train_production(df: pd.DataFrame, model_name: str = "blend", window: int | None = None, before: int | None = None):
    """Fit the production model on every finished season (or only those before `before`, for
    honest backtests). Returns (model, seasons_used)."""
    train_df = add_target(finished_seasons(df))
    if before is not None:
        train_df = train_df[train_df["season"] < before]
    seasons = sorted(s for s in train_df["season"].unique() if train_df[train_df["season"] == s]["committee_rank"].notna().any())
    if window:
        seasons = seasons[-window:]
    train = train_df[train_df["season"].isin(seasons)]
    return make_models()[model_name].fit(train[FEATURES], train["target"]), seasons


def predict_current(df: pd.DataFrame, model_name: str = "blend", window: int | None = None) -> pd.DataFrame:
    current_season = int(df["season"].max())
    model, train_seasons = train_production(df, model_name, window)

    now = df[df["season"] == current_season]
    now = now[now["ranking_week"] == now["ranking_week"].max()].copy()
    now["predicted_score"] = model.predict(now[FEATURES])
    now = now.sort_values(["predicted_score", "elo_current"], ascending=False).reset_index(drop=True)
    now["predicted_seed"] = now.index + 1
    print(f"Trained on {train_seasons[0]}-{train_seasons[-1]} ({len(train_seasons)} seasons), model={model_name}")
    return now


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["backtest", "field-backtest", "predict"])
    args = parser.parse_args()
    df = load_features()
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    if args.command == "backtest":
        results = backtest(df)
        results.to_csv(RESULT_DIR / "backtest_details.csv", index=False)
        summary = summarize(results)
        summary.to_csv(RESULT_DIR / "backtest_summary.csv")
        print("Average over test seasons (final week = Selection Day list). Max possible top12 = 12, top4 = 4.\n")
        print(summary.to_string())
    elif args.command == "field-backtest":
        res = backtest_field(df)
        res.to_csv(RESULT_DIR / "field_backtest_details.csv", index=False)
        print("Teams correct out of 12 (and byes out of 4) vs the TRUE playoff field.\n")
        by = res.groupby(["rule", "method"])[["field_correct", "byes_correct"]].agg(["mean", "count"]).round(2)
        print(by.to_string())
        print("\nReal-rule seasons only:")
        print(res[res["season"].isin([2024, 2025]) & (res["rule"] == res["season"].astype(str))].to_string(index=False))
    else:
        pred = predict_current(df)
        week = int(pred["ranking_week"].iloc[0])

        ranking_cols = ["predicted_seed", "team", "conference", "wins", "losses", "sos", "quality_wins", "elo_current", "ref_ap_rank", "conf_champion"]
        pred[ranking_cols].head(25).to_csv(RESULT_DIR / "ranking_2026.csv", index=False)

        field = select_field(as_ranked_table(pred, pred["predicted_seed"].astype(float)), "2026")
        field = field.merge(pred[["team", "wins", "losses"]], on="team")
        field["record"] = field["wins"].astype(str) + "-" + field["losses"].astype(str)
        out_cols = ["seed", "team", "conference", "record", "reason", "rank"]
        field[out_cols].to_csv(RESULT_DIR / "prediction_2026.csv", index=False)
        # Keep every week's prediction so we can later score how it evolved against the committee.
        history = RESULT_DIR / "history"
        history.mkdir(exist_ok=True)
        field[out_cols].to_csv(history / f"prediction_2026_week{week:02d}.csv", index=False)
        pred[ranking_cols].head(25).to_csv(history / f"ranking_2026_week{week:02d}.csv", index=False)

        print(f"\nPredicted 2026 playoff field as of ranking week {week} (2026 rules).")
        print("Champions are PROJECTED from current conference standings until the title games are played.")
        print("Seeding assumes seeds follow the ranking (the 2026 seeding rule was not in the announcement).\n")
        print(field[["seed", "team", "conference", "record", "reason"]].to_string(index=False))


if __name__ == "__main__":
    main()
