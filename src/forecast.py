"""Forecast the committee's NEXT list (model v3), save it before the list is released, then score it.

The committee is sticky: it mostly nudges its previous list rather than re-ranking from scratch.
So the best forecast of Tuesday's list uses this weekend's results AND the committee's last list.
Each forecast is saved to data/results/forecasts/ before the committee publishes, so scoring it
afterwards is a genuine out-of-sample test (check the commit times in git).

Usage:
    python -m src.forecast             # forecast the upcoming list, score past forecasts, update README
    python -m src.forecast backtest    # how well would this have worked in past seasons?
"""
import argparse
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from src.model import (
    FEATURES, FEATURES_V3, RESULT_DIR, add_target, finished_seasons, load_features, make_models,
    score_prediction, top_field, train_production,
)
from src.report import README, replace_block

FORECAST_DIR = RESULT_DIR / "forecasts"
START = "<!-- FORECAST:START -->"
END = "<!-- FORECAST:END -->"
FIRST_TEST_SEASON = 2017


def actual_top12(week_df: pd.DataFrame) -> list[str]:
    return week_df.dropna(subset=["committee_rank"]).sort_values("committee_rank")["team"].head(12).tolist()


def repeat_last_list(week_df: pd.DataFrame) -> list[str]:
    """The do-nothing forecast: the committee's previous top 12."""
    return week_df[week_df["last_list_rank"] <= 12].sort_values("last_list_rank")["team"].tolist()


# ---------- live forecast ----------

def make_forecast(df: pd.DataFrame) -> tuple[int, pd.DataFrame] | None:
    """Forecast the next list. Returns None if the newest snapshot's list is already published."""
    season = df[df["season_complete"] == 0]
    week = int(season["ranking_week"].max())
    snap = season[season["ranking_week"] == week].copy()
    if snap["committee_rank"].notna().any():
        return None  # that list is already out; wait for the next games
    if snap["last_list_rank"].isna().all():
        return None  # no committee list exists yet, so there is nothing to build on
    model, _ = train_production(df, features=FEATURES_V3)
    snap["score"] = model.predict(snap[FEATURES_V3])
    snap = snap.sort_values(["score", "elo_current"], ascending=False).reset_index(drop=True)
    snap["predicted_rank"] = snap.index + 1
    snap["record"] = snap["wins"].astype(str) + "-" + snap["losses"].astype(str)
    return week, snap[["predicted_rank", "team", "conference", "record", "last_list_rank", "score"]].head(25)


def save_forecast(week: int, forecast: pd.DataFrame) -> None:
    FORECAST_DIR.mkdir(parents=True, exist_ok=True)
    out = forecast.assign(forecast_made_utc=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"))
    out.to_csv(FORECAST_DIR / f"forecast_week{week:02d}.csv", index=False)


# ---------- scoring saved forecasts ----------

def score_saved_forecasts(df: pd.DataFrame) -> pd.DataFrame:
    season = df[df["season_complete"] == 0]
    v1, _ = train_production(df)
    rows = []
    for path in sorted(FORECAST_DIR.glob("forecast_week*.csv")):
        week = int(path.stem.rsplit("week", 1)[1])
        w = season[season["ranking_week"] == week]
        if w["committee_rank"].notna().sum() < 12:
            continue  # the committee hasn't published that list yet
        actual = actual_top12(w)
        saved = pd.read_csv(path)
        predicted = saved.sort_values("predicted_rank")["team"].head(12).tolist()
        methods = {
            "v3_forecast": predicted,
            "repeat_last_list": repeat_last_list(w),
            "model_v1": top_field(w, pd.Series(v1.predict(w[FEATURES]), index=w.index)),
        }
        for name, teams in methods.items():
            rows.append({"list_week": week, "method": name, **score_prediction(teams, actual),
                         "forecast_made_utc": saved["forecast_made_utc"].iloc[0]})
    return pd.DataFrame(rows)


# ---------- backtest ----------

def backtest(df: pd.DataFrame) -> pd.DataFrame:
    """Walk-forward: for each past committee list, forecast it from the previous list + results."""
    d = add_target(finished_seasons(df))
    d = d[d.groupby(["season", "ranking_week"])["committee_rank"].transform(lambda s: s.notna().any())]
    seasons = sorted(d["season"].unique())
    rows = []
    for year in [s for s in seasons if s >= FIRST_TEST_SEASON]:
        train = d[d["season"] < year]
        v1 = make_models()["blend"].fit(train[FEATURES], train["target"])
        v3 = make_models()["blend"].fit(train[FEATURES_V3], train["target"])
        for week, w in d[(d["season"] == year) & d["last_list_week"].notna()].groupby("ranking_week"):
            actual = actual_top12(w)
            methods = {
                "model_v1": top_field(w, pd.Series(v1.predict(w[FEATURES]), index=w.index)),
                "v3_forecast": top_field(w, pd.Series(v3.predict(w[FEATURES_V3]), index=w.index)),
                "repeat_last_list": repeat_last_list(w),
            }
            for name, teams in methods.items():
                rows.append({"season": year, "list_week": week, "method": name, **score_prediction(teams, actual)})
    return pd.DataFrame(rows)


def summarize_backtest(res: pd.DataFrame) -> dict:
    wide = res.pivot_table(index=["season", "list_week"], columns="method", values="top12_correct")
    gain = wide["v3_forecast"] - wide["model_v1"]
    return {
        "lists": len(wide),
        "v3": wide["v3_forecast"].mean(), "v1": wide["model_v1"].mean(), "repeat": wide["repeat_last_list"].mean(),
        "gain": gain.mean(), "gain_se": gain.std() / np.sqrt(len(gain)),
        "better": int((gain > 0).sum()), "same": int((gain == 0).sum()), "worse": int((gain < 0).sum()),
        "seed_v3": res[res["method"] == "v3_forecast"]["seed_error"].mean(),
        "seed_v1": res[res["method"] == "model_v1"]["seed_error"].mean(),
    }


# ---------- README ----------

def render_block(week: int | None, forecast: pd.DataFrame | None, scores: pd.DataFrame, bt: dict | None, why: str = "") -> str:
    lines = [START]
    if forecast is not None:
        made = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        lines += [
            f"**Forecast of the committee's week {week} list**, made {made} from this week's results and the",
            f"committee's last list. It is saved before the list is released, then scored below.",
            "",
            "| Predicted rank | Team | Record | Committee's last rank |",
            "|---:|---|---|---:|",
        ]
        for r in forecast.head(15).itertuples():
            last = "unranked" if r.last_list_rank >= 40 else f"{int(r.last_list_rank)}"
            lines.append(f"| {r.predicted_rank} | {r.team} | {r.record} | {last} |")
        if why:
            lines += ["", why]
    else:
        lines.append("*Waiting for new games: the committee's latest list has already been published.*")

    lines += ["", "**Scored forecasts** (top 12 correct out of 12):", ""]
    if scores.empty:
        lines.append("*None yet. The first forecast is scored once the committee releases its list.*")
    else:
        pivot = scores.pivot(index="list_week", columns="method", values="top12_correct")
        top4 = scores[scores["method"] == "v3_forecast"].set_index("list_week")["top4_correct"]
        lines += ["| Committee list | v3 forecast | Repeat last list | v1 résumé model | v3 top 4 right |", "|---:|---:|---:|---:|---:|"]
        for wk in pivot.index:
            lines.append(f"| week {wk} | {pivot.loc[wk, 'v3_forecast']:.0f} / 12 | {pivot.loc[wk, 'repeat_last_list']:.0f} / 12 | {pivot.loc[wk, 'model_v1']:.0f} / 12 | {top4[wk]:.0f} / 4 |")
        lines.append(f"| **Average** | **{pivot['v3_forecast'].mean():.1f}** | **{pivot['repeat_last_list'].mean():.1f}** | **{pivot['model_v1'].mean():.1f}** | **{top4.mean():.1f} / 4** |")
    if bt:
        lines += [
            "",
            f"*Backtest, {bt['lists']} past committee lists forecast one week ahead:* v3 {bt['v3']:.1f}/12, "
            f"résumé model {bt['v1']:.1f}/12, repeat-last-list {bt['repeat']:.1f}/12. v3 beat v1 on {bt['better']} lists, "
            f"tied on {bt['same']}, lost on {bt['worse']} (gain {bt['gain']:+.2f} teams, {bt['gain'] / bt['gain_se']:.1f} standard errors).",
        ]
    lines.append(END)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", default="run", choices=["run", "backtest"])
    args = parser.parse_args()
    df = load_features()
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    if args.command == "backtest":
        res = backtest(df)
        res.to_csv(RESULT_DIR / "forecast_backtest_details.csv", index=False)
        s = summarize_backtest(res)
        pd.Series(s).to_csv(RESULT_DIR / "forecast_backtest_summary.csv", header=["value"])
        print(f"{s['lists']} past committee lists, forecast one week ahead (top 12 right, of 12):")
        print(f"  v3 (results + last list): {s['v3']:.2f}   seed error {s['seed_v3']:.2f}")
        print(f"  v1 (results only):        {s['v1']:.2f}   seed error {s['seed_v1']:.2f}")
        print(f"  repeat last list:         {s['repeat']:.2f}")
        print(f"  v3 vs v1: better {s['better']}, same {s['same']}, worse {s['worse']}; gain {s['gain']:+.2f} (SE {s['gain_se']:.2f})")
        return

    made = make_forecast(df)
    week, forecast = made if made else (None, None)
    if made:
        save_forecast(week, forecast)
        forecast.to_csv(RESULT_DIR / "forecast_next_list.csv", index=False)
        print(f"Forecast for the week {week} committee list saved.\n")
        print(forecast.head(12).round(2).to_string(index=False))
    else:
        print("No new forecast: the newest list is already published.")

    scores = score_saved_forecasts(df)
    scores.to_csv(RESULT_DIR / "forecast_scorecard.csv", index=False)
    summary_path = RESULT_DIR / "forecast_backtest_summary.csv"
    bt = pd.read_csv(summary_path, index_col=0)["value"].to_dict() if summary_path.exists() else None
    if bt:
        bt = {k: (int(v) if k in ("lists", "better", "same", "worse") else float(v)) for k, v in bt.items()}
    why = ""
    if made:
        from src.explain import forecast_why, team_table

        season = df[df["season_complete"] == 0]
        snap = season[season["ranking_week"] == week]
        games = pd.read_csv(RESULT_DIR.parent / "clean" / f"team_games_{int(snap['season'].iloc[0])}.csv")
        why = forecast_why(forecast, team_table(snap, games))
    text = README.read_text(encoding="utf-8")
    README.write_text(replace_block(text, render_block(week, forecast, scores, bt, why), START, END), encoding="utf-8")


if __name__ == "__main__":
    main()
