"""Plain-English explanations for the README, generated from the same data as the tables.

Nothing here is hand-written per team or per week: every sentence is built from numbers the
pipeline already computed, so the explanations update with each GitHub Action and cannot drift
away from the tables they sit under. Terms are kept simple for readers who don't follow football
(see the glossary in the README).
"""
from pathlib import Path

import numpy as np
import pandas as pd

CLEAN_DIR = Path(__file__).resolve().parent.parent / "data" / "clean"

# How big a gap must be before we call it a real advantage when comparing two teams.
GAPS = {"losses": 1, "schedule": 10, "big_wins": 1, "margin": 2.5, "rating": 50}


def ordinal(n: int) -> str:
    n = int(n)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def plural(n: int, word: str) -> str:
    return f"{int(n)} {word}{'' if int(n) == 1 else 's'}"


def team_table(snap: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """One row per team with the plain-language facts used in every explanation.

    snap  = the team's latest résumé snapshot (data/features); games = its completed games.
    """
    t = snap.set_index("team").copy()
    n = len(t)
    t["record"] = t["wins"].astype(int).astype(str) + "-" + t["losses"].astype(int).astype(str)
    t["schedule_rank"] = t["sos_now"].rank(ascending=False, method="min").astype(int)  # 1 = hardest
    t["n_teams"] = n
    t["big_wins"] = t["quality_wins_now"].astype(int)

    rating = t["elo_current"]
    g = games[games["season_type"] == "regular"].copy()
    g["opp_rating"] = g["opponent"].map(rating)
    wins = g[(g["result"] == 1) & g["opp_rating"].notna()]
    losses = g[(g["result"] == 0) & g["opp_rating"].notna()]
    t["best_win"] = wins.loc[wins.groupby("team")["opp_rating"].idxmax()].set_index("team")["opponent"]
    t["worst_loss"] = losses.loc[losses.groupby("team")["opp_rating"].idxmin()].set_index("team")["opponent"]

    last = g.sort_values(["week", "start_date"]).groupby("team").tail(1).set_index("team")
    where = np.where(last["neutral_site"].astype(bool), "vs", np.where(last["is_home"].astype(bool), "vs", "at"))
    opp_rank = last["opponent"].map(t["last_list_rank"]) if "last_list_rank" in t else pd.Series(np.nan, index=last.index)
    opp = np.where(opp_rank.between(1, 25), "#" + opp_rank.round().astype("Int64").astype(str) + " ", "") + last["opponent"]
    t["last_game"] = (
        np.where(last["result"] == 1, "won", "lost") + " "
        + last["points_for"].astype(int).astype(str) + "-" + last["points_against"].astype(int).astype(str)
        + " " + where + " " + opp
    ).reindex(t.index)
    return t


def resume_line(row: pd.Series) -> str:
    """A one-line résumé: record, how hard the schedule was, how many big wins."""
    line = (
        f"{row['record']}, {ordinal(row['schedule_rank'])}-hardest schedule of {int(row['n_teams'])}, "
        f"{plural(row['big_wins'], 'big win')}"
    )
    if isinstance(row.get("best_win"), str):
        line += f" (best: {row['best_win']})" if row["big_wins"] else ""
    return line


def advantages(a: pd.Series, b: pd.Series) -> list[str]:
    """Reasons team a looks better than team b (at most two, strongest signals only)."""
    out = []
    if a["losses"] + GAPS["losses"] <= b["losses"]:
        out.append(f"fewer losses ({int(a['losses'])} vs {int(b['losses'])})")
    if a["schedule_rank"] + GAPS["schedule"] <= b["schedule_rank"]:
        out.append(f"a harder schedule ({ordinal(a['schedule_rank'])} vs {ordinal(b['schedule_rank'])} hardest)")
    if a["big_wins"] >= b["big_wins"] + GAPS["big_wins"]:
        out.append(f"more big wins ({int(a['big_wins'])} vs {int(b['big_wins'])})")
    if a["avg_margin"] >= b["avg_margin"] + GAPS["margin"]:
        out.append("bigger typical winning margins")
    if a["elo_current"] >= b["elo_current"] + GAPS["rating"]:
        out.append("a higher overall power rating")
    return out[:2]


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else " and ".join(items)


def compare_line(inside: str, outside: str, t: pd.DataFrame) -> str:
    a, b = t.loc[inside], t.loc[outside]
    why_in = advantages(a, b)
    why_out = advantages(b, a)
    parts = [f"**{inside}** ({a['record']}) is the last team in; **{outside}** ({b['record']}) is the first team out."]
    if why_in:
        parts.append(f"{inside} has {_join(why_in)}.")
    if why_out:
        parts.append(f"{outside} has {_join(why_out)}.")
    if not why_in and not why_out:
        parts.append("They are nearly identical on paper, so this is close to a coin flip.")
    return " ".join(parts)


# ---------- section: predicted playoff field ----------

def field_why(field: pd.DataFrame, ranking: pd.DataFrame, t: pd.DataFrame) -> str:
    """Why these 12 teams: automatic spots, at-large spots, and the cut line."""
    auto = field[field["auto_bid"] if "auto_bid" in field else field["reason"] != "at-large"]
    lines = ["**Why these 12?**", ""]
    if len(auto):
        # Some reasons already name the team (e.g. "Notre Dame (ranked top 12)"); don't repeat it.
        names = ", ".join(r.reason if r.reason.startswith(r.team) else f"{r.team} ({r.reason})" for r in auto.itertuples())
        lines.append(
            f"- **Automatic spots** go to conference champions, no matter how they rank: {names}. "
            "Until the conference title games are played, each \"champion\" here is just the current leader."
        )
    lines.append("- **The remaining spots** go to the highest-ranked teams (by the model) that aren't already in.")
    low_auto = auto[auto["rank"] > 12]
    if len(low_auto):
        names = ", ".join(f"{r.team} (ranked {ordinal(r.rank)})" for r in low_auto.itertuples())
        verb = "is" if len(low_auto) == 1 else "are"
        lines.append(f"- An automatic spot can beat a better-ranked team: {names} {verb} in on the champion rule alone, which takes a spot from an at-large team.")

    at_large = field[field["reason"] == "at-large"]
    outside = ranking[~ranking["team"].isin(field["team"])]
    if len(at_large) and len(outside):
        last_in, first_out = at_large.iloc[-1]["team"], outside.sort_values("predicted_seed").iloc[0]["team"]
        if last_in in t.index and first_out in t.index:
            lines.append(f"- **The closest call:** {compare_line(last_in, first_out, t)}")
    lines += ["", "<details><summary>Each team's résumé</summary>", "", "| Seed | Team | Résumé |", "|---:|---|---|"]
    for r in field.itertuples():
        lines.append(f"| {r.seed} | {r.team} | {resume_line(t.loc[r.team]) if r.team in t.index else ''} |")
    lines += ["", "*Big win = a win over a team in the top fifth of the sport by power rating.*", "</details>"]
    return "\n".join(lines)


# ---------- section: simulated odds ----------

def simulation_why(result: pd.DataFrame) -> str:
    """What the odds depend on, using each team's chances if they win out vs. slip once."""
    lines = ["**What do these odds depend on?**", ""]
    locks = result[result["p_field"] >= 0.99]
    if len(locks):
        lines.append(f"- **Nearly locked in (99%+):** {', '.join(locks['team'])}. Even a bad finish probably wouldn't cost them.")
    mid = result[result["p_field"].between(0.10, 0.90)].copy()
    mid["closeness"] = (mid["p_field"] - 0.5).abs()
    shown = 0
    for r in mid.sort_values("closeness").head(6).itertuples():
        if pd.notna(r.p_field_if_win_out) and pd.notna(r.p_field_if_loses):
            lines.append(
                f"- **{r.team}** ({r.record}, {plural(r.games_left, 'game')} left): {r.p_field:.0%} overall, "
                f"**{r.p_field_if_win_out:.0%} if they win out**, {r.p_field_if_loses:.0%} if they lose at least once."
            )
            shown += 1
    if not shown:
        lines.append("- No team is on the bubble in a way the simulations can separate (too few games left).")
    long_shots = result[(result["p_field"] > 0) & (result["p_field"] < 0.10) & (result["p_conf_champion"] > 0.3)]
    if len(long_shots):
        lines.append(
            f"- **Long shots that could sneak in by winning their conference:** {', '.join(long_shots['team'].head(4))}. "
            "Under the 2026 rules the best champion from outside the big four conferences gets an automatic spot."
        )
    lines.append("- Teams in the middle are the ones whose last games decide the field. Teams near 0% or 100% mostly won't move.")
    return "\n".join(lines)


# ---------- section: scorecard (where the model and committee disagree) ----------

def scorecard_why(week_df: pd.DataFrame, model_score: pd.Series, t: pd.DataFrame, week: int) -> str:
    """Explain the latest disagreements between the model and the committee."""
    w = week_df.copy()
    w["model_rank"] = model_score.rank(ascending=False, method="first").astype(int)
    committee_top = w[w["committee_rank"] <= 12]
    model_top = w[w["model_rank"] <= 12]
    missed = committee_top[~committee_top["team"].isin(model_top["team"])].sort_values("committee_rank")
    wrong = model_top[~model_top["team"].isin(committee_top["team"])].sort_values("model_rank")
    lines = [f"**Why did the model miss on week {week}?**", ""]

    both = w[w["committee_rank"].notna() & w["last_list_rank"].between(1, 25)]
    if len(both) >= 5:
        moves = (both["committee_rank"] - both["last_list_rank"]).abs()
        lines.append(
            f"- **The committee barely re-ranks.** Among teams on both of its last two lists, the typical team moved "
            f"{plural(moves.median(), 'spot')} and {int((moves == 0).sum())} of {len(both)} didn't move at all. "
            "The model rebuilds its ranking from scratch each week, so it disagrees most about teams the committee is simply leaving alone."
        )

    def line(r, kind):
        info = t.loc[r.team] if r.team in t.index else None
        prev = f" (was {ordinal(r.last_list_rank)} last list)" if r.last_list_rank <= 25 else " (unranked last list)"
        stats = f" {resume_line(info)}." if info is not None else ""
        if kind == "missed":
            return f"- **{r.team}**: the committee has them {ordinal(r.committee_rank)}{prev}; the model has them {ordinal(r.model_rank)}.{stats}"
        committee = f"{ordinal(r.committee_rank)}" if pd.notna(r.committee_rank) else "outside its top 25"
        return f"- **{r.team}**: the model has them {ordinal(r.model_rank)}; the committee has them {committee}{prev}.{stats}"

    if len(missed):
        lines.append("- **In the committee's top 12 but not the model's:**")
        lines += ["  " + line(r, "missed") for r in missed.itertuples()]
    if len(wrong):
        lines.append("- **In the model's top 12 but not the committee's:**")
        lines += ["  " + line(r, "wrong") for r in wrong.itertuples()]
    if not len(missed) and not len(wrong):
        lines.append("- The model's top 12 matched the committee's exactly.")
    return "\n".join(lines)


# ---------- section: next-list forecast ----------

def forecast_why(forecast: pd.DataFrame, t: pd.DataFrame) -> str:
    """Why the forecast moves teams: last week's result, against the committee's last list."""
    f = forecast.copy()
    f["move"] = f["last_list_rank"].where(f["last_list_rank"] <= 25) - f["predicted_rank"]
    top12 = f.head(12)
    same = int((top12["move"] == 0).sum())
    close = int((top12["move"].abs() <= 2).sum())
    lines = [
        "**Why does the forecast look like this?**", "",
        f"- The committee rarely changes its mind much, so the forecast starts from its last list. {close} of the top 12 "
        f"are predicted to land within two spots of where the committee already had them ({same} in the exact same spot).",
        "- Then it adjusts for this week's results. The biggest expected moves in the top 25:",
    ]
    movers = f[(f["move"].abs() >= 3) | f["move"].isna()].copy()
    movers["size"] = movers["move"].abs().fillna(99)
    shown = 0
    for r in movers.sort_values("size", ascending=False).head(6).itertuples():
        game = t.loc[r.team, "last_game"] if r.team in t.index else ""
        if pd.isna(r.move):
            lines.append(f"  - **{r.team}** comes in at {r.predicted_rank} (unranked last list): {game}.")
        else:
            arrow = "up" if r.move > 0 else "down"
            lines.append(f"  - **{r.team}** {arrow} {int(abs(r.move))} to {r.predicted_rank} (was {int(r.last_list_rank)}): {game}.")
        shown += 1
    if not shown:
        lines.append("  - No team is expected to move more than two spots.")
    return "\n".join(lines)
