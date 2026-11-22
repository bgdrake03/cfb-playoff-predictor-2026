"""Score the models against the committee's real 2026 lists as they are published.

Model v1 is tagged `model-v1` (Oct 17), before the committee published any 2026 list, so it is a
genuine out-of-sample test. Later commits only fixed data plumbing.

Model v2 adds conference-strength features. It was designed AFTER weeks 10-12 were published, so
those weeks are marked and excluded from v2's average; only later lists are a fair test of v2.

Usage:
    python -m src.scorecard          # writes data/results/scorecard_2026.csv and updates README
"""
import pandas as pd

import src.model as model_module
from src.model import FEATURES, FEATURES_V2, baseline_scores, load_features, score_prediction, top_field, train_production
from src.report import README, replace_block

START = "<!-- SCORECARD:START -->"
END = "<!-- SCORECARD:END -->"
V2_DESIGNED_AFTER_WEEK = 12  # v2 was built after seeing committee lists through this week


def score_current_season(df: pd.DataFrame) -> pd.DataFrame:
    v1, _ = train_production(df)
    v2, _ = train_production(df, features=FEATURES_V2)
    season = df[df["season_complete"] == 0]
    rows = []
    for week, w in season.groupby("ranking_week"):
        committee = w.dropna(subset=["committee_rank"]).sort_values("committee_rank")
        if len(committee) < 12:
            continue  # the committee hasn't released this week's list yet
        actual = committee["team"].head(12).tolist()
        methods = {
            "model_v1": pd.Series(v1.predict(w[FEATURES]), index=w.index),
            "model_v2": pd.Series(v2.predict(w[FEATURES_V2]), index=w.index),
            **baseline_scores(w),
        }
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
    top4 = scores[scores["method"] == "model_v1"].set_index("ranking_week")["top4_correct"]
    fair_v2 = pivot.index[pivot.index > V2_DESIGNED_AFTER_WEEK]
    lines += [
        "Committee's real top 12 vs. the model. **v1** was frozen on Oct 17 (git tag `model-v1`), before the",
        "committee's first 2026 list. **v2** adds conference strength and was designed after week 12, so",
        "weeks marked * are not a fair test of v2 and are left out of its average.",
        "",
        "| Committee week | v1: top 12 right | v2: top 12 right | AP poll: top 12 right | v1: top 4 right |",
        "|---:|---:|---:|---:|---:|",
    ]
    for week in pivot.index:
        star = "*" if week <= V2_DESIGNED_AFTER_WEEK else ""
        lines.append(f"| {week} | {pivot.loc[week, 'model_v1']:.0f} / 12 | {pivot.loc[week, 'model_v2']:.0f}{star} / 12 | {pivot.loc[week, 'ap_poll']:.0f} / 12 | {top4[week]:.0f} / 4 |")
    v2_avg = f"{pivot.loc[fair_v2, 'model_v2'].mean():.1f} / 12 ({len(fair_v2)} wk)" if len(fair_v2) else "not enough weeks yet"
    lines.append(f"| **Average** | **{pivot['model_v1'].mean():.1f} / 12** | **{v2_avg}** | **{pivot['ap_poll'].mean():.1f} / 12** | **{top4.mean():.1f} / 4** |")
    latest = scores[(scores["method"] == "model_v1") & (scores["ranking_week"] == scores["ranking_week"].max())].iloc[0]
    lines += ["", f"Latest list (week {int(latest['ranking_week'])}): v1 missed {latest['missed'] or 'nobody'}; v1 wrongly included {latest['wrongly_in'] or 'nobody'}.", END]
    return "\n".join(lines)


def main() -> None:
    df = load_features()
    scores = score_current_season(df)
    scores.to_csv(model_module.RESULT_DIR / "scorecard_2026.csv", index=False)
    text = README.read_text(encoding="utf-8")
    README.write_text(replace_block(text, render_block(scores), START, END), encoding="utf-8")
    show = scores[scores["method"].isin(["model_v1", "model_v2", "ap_poll"])]
    print(show.pivot(index="ranking_week", columns="method", values="top12_correct").to_string())


if __name__ == "__main__":
    main()
