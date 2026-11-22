"""Score the FROZEN model against the committee's real 2026 lists as they are published.

The model is tagged `model-v1` (Oct 17), so this is a genuine out-of-sample test: its definition was
fixed before the committee published any 2026 list. Later commits only fixed data plumbing. For each ranking week the committee has released,
we compare the model's top 12 with the committee's top 12, next to some baselines.

Usage:
    python -m src.scorecard          # writes data/results/scorecard_2026.csv and updates README
"""
import pandas as pd

from src.model import FEATURES, baseline_scores, load_features, score_prediction, top_field, train_production
from src.report import README, replace_block

import src.model as model_module

START = "<!-- SCORECARD:START -->"
END = "<!-- SCORECARD:END -->"


def score_current_season(df: pd.DataFrame) -> pd.DataFrame:
    model, _ = train_production(df)
    season = df[df["season_complete"] == 0]
    rows = []
    for week, w in season.groupby("ranking_week"):
        committee = w.dropna(subset=["committee_rank"]).sort_values("committee_rank")
        if len(committee) < 12:
            continue  # the committee hasn't released this week's list yet
        actual = committee["team"].head(12).tolist()
        methods = {"model": pd.Series(model.predict(w[FEATURES]), index=w.index), **baseline_scores(w)}
        for name, score in methods.items():
            predicted = top_field(w, score)
            rows.append(
                {"ranking_week": week, "method": name, **score_prediction(predicted, actual),
                 "missed": "; ".join(t for t in actual if t not in predicted),
                 "wrongly_in": "; ".join(t for t in predicted if t not in actual)}
            )
    return pd.DataFrame(rows)


def render_block(scores: pd.DataFrame) -> str:
    lines = [START]
    if scores.empty:
        lines += ["*The committee has not released a 2026 list yet.*", END]
        return "\n".join(lines)
    pivot = scores.pivot(index="ranking_week", columns="method", values="top12_correct")
    top4 = scores[scores["method"] == "model"].set_index("ranking_week")["top4_correct"]
    lines += [
        "Model frozen on Oct 17 (git tag `model-v1`), before the committee's first 2026 list, vs. the committee's real top 12.",
        "Later commits only fixed data plumbing (the latest-week snapshot); the model itself is unchanged:",
        "",
        "| Committee week | Model: top 12 right | AP poll: top 12 right | Model: top 4 right |",
        "|---:|---:|---:|---:|",
    ]
    for week in pivot.index:
        lines.append(f"| {week} | {pivot.loc[week, 'model']:.0f} / 12 | {pivot.loc[week, 'ap_poll']:.0f} / 12 | {top4[week]:.0f} / 4 |")
    lines.append(f"| **Average** | **{pivot['model'].mean():.1f} / 12** | **{pivot['ap_poll'].mean():.1f} / 12** | **{top4.mean():.1f} / 4** |")
    latest = scores[(scores["method"] == "model") & (scores["ranking_week"] == scores["ranking_week"].max())].iloc[0]
    lines += ["", f"Latest list (week {int(latest['ranking_week'])}): model missed {latest['missed'] or 'nobody'}; model wrongly included {latest['wrongly_in'] or 'nobody'}.", END]
    return "\n".join(lines)


def main() -> None:
    df = load_features()
    scores = score_current_season(df)
    scores.to_csv(model_module.RESULT_DIR / "scorecard_2026.csv", index=False)
    text = README.read_text(encoding="utf-8")
    README.write_text(replace_block(text, render_block(scores), START, END), encoding="utf-8")
    print(scores[scores["method"].isin(["model", "ap_poll"])][["ranking_week", "method", "top12_correct", "top4_correct", "missed", "wrongly_in"]].to_string(index=False))


if __name__ == "__main__":
    main()
