"""Monte Carlo simulation of the rest of the regular season, through Selection Day.

A single prediction treats today's standings as final. This instead plays the remaining games
thousands of times, crowns conference champions (title games included), runs the frozen model
and the 2026 selection rules on each simulated final record, and reports PROBABILITIES:
how often each team makes the 12-team field, earns a bye, or wins its conference.

Game model (fitted on 2021-2025 FBS-vs-FBS games; see the calibration notes below):
  margin ~ Normal(0.0417 * Elo_diff + 3.42 * home, sd 16.4); the winner is the sign of the margin.
  This reproduces the observed win rates in every probability bucket within ~2 points.
  Elo moves after each game by K * (result - expected), K ~ 60.

Simplifications (deliberate, and listed so they can be improved):
  - Elo ratings are held fixed within a simulated season when predicting later games;
    they are only updated at the end (for the model's elo_current feature).
  - Each conference's title game is between its top two teams by conference record, with ties
    broken by Elo rather than the conference's real tiebreakers. Every conference is assumed
    to hold a title game (Independents have none).
  - FCS opponents get a fixed placeholder rating and are never updated.

Usage:
    python -m src.simulate --sims 1000
"""
import argparse
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

from src.features import FCS_ELO, add_game_quality, snapshot
from src.field import select_field
from src.model import FEATURES, RESULT_DIR, as_ranked_table, load_features, train_production
from src.report import README, replace_block

CLEAN_DIR = Path(__file__).resolve().parent.parent / "data" / "clean"

MARGIN_PER_ELO = 0.0417
HOME_MARGIN = 3.42
MARGIN_SD = 16.39
ELO_K = 60.0

SELECTION_DATE = "2026-12-06"  # games after this (e.g. Army-Navy) don't affect the field
TITLE_WEEK = 14  # default title-game week when no games remain
YEAR = 2026


def win_prob(expected_margin: np.ndarray) -> np.ndarray:
    """P(margin > 0) for a Normal(expected_margin, MARGIN_SD) game."""
    return 0.5 * (1 + np.vectorize(erf)(expected_margin / (MARGIN_SD * sqrt(2))))


class Context:
    """Everything that stays fixed across simulations.

    By default this is the current season, from today. For backtests, pass `as_of_week` to
    rewind to a past ranking week (using only games before it, and a model trained only on
    earlier seasons).
    """

    def __init__(self, year: int = YEAR, selection_date: str = SELECTION_DATE, as_of_week: int | None = None,
                 train_before: int | None = None, rule: str = "2026"):
        df = load_features()
        self.year, self.rule, self.as_of_week = year, rule, as_of_week
        season = df[df["season"] == year]
        if as_of_week is None:
            season = season[season["season_complete"] == 0]
            as_of_week = season["ranking_week"].max()
        self.snapshot_df = season[season["ranking_week"] == as_of_week]
        self.elo = self.snapshot_df.set_index("team")["elo_current"].astype(float)
        self.conference = self.snapshot_df.set_index("team")["conference"]

        played = pd.read_csv(CLEAN_DIR / f"team_games_{year}.csv")
        played = played[played["season_type"] == "regular"]
        if self.as_of_week is not None:
            played = played[played["week"] <= as_of_week - 1]
        self.played = played.copy()

        if self.as_of_week is None:
            up = pd.read_csv(CLEAN_DIR / f"upcoming_{year}.csv")
            up = up[(up["seasonType"] == "regular") & (up["startDate"].str[:10] < selection_date)]
        else:
            up = self._historical_schedule(year, as_of_week, final_week=int(df.loc[df["season"] == year, "ranking_week"].max()))
        self.upcoming = up.reset_index(drop=True)
        self.title_week = int(self.upcoming["week"].max()) + 1 if len(self.upcoming) else TITLE_WEEK
        up = self.upcoming

        # Fixed arrays for the remaining games
        self.home_elo = up["homeTeam"].map(self.elo).fillna(FCS_ELO).to_numpy(float)
        self.away_elo = up["awayTeam"].map(self.elo).fillna(FCS_ELO).to_numpy(float)
        self.home_adv = (~up["neutralSite"].astype(bool)).to_numpy(float)
        self.mean_margin = MARGIN_PER_ELO * (self.home_elo - self.away_elo) + HOME_MARGIN * self.home_adv
        self.p_home = win_prob(self.mean_margin)
        self.home_fbs = (up["homeClassification"] == "fbs").to_numpy()
        self.away_fbs = (up["awayClassification"] == "fbs").to_numpy()

        # Conference record so far (conference games only)
        conf_rows = self.played[self.played["conference_game"]]
        self.conf_wins0 = conf_rows.groupby("team")["result"].sum().reindex(self.elo.index, fill_value=0)
        self.conf_games0 = conf_rows.groupby("team").size().reindex(self.elo.index, fill_value=0)

        self.model, self.train_seasons = train_production(df, before=train_before)
        self.teams = list(self.elo.index)

    @staticmethod
    def _historical_schedule(year: int, as_of_week: int, final_week: int) -> pd.DataFrame:
        """The real games between `as_of_week` and Selection Day, minus conference title games
        (the simulator creates its own title games from the simulated standings)."""
        raw = pd.read_csv(CLEAN_DIR.parent / "raw" / f"games_{year}.csv")
        raw = raw[(raw["seasonType"] == "regular") & raw["week"].between(as_of_week, final_week - 1)]
        raw = raw[(raw["homeClassification"] == "fbs") | (raw["awayClassification"] == "fbs")]
        same_conf = (raw["homeConference"] == raw["awayConference"]) & (raw["homeConference"] != "FBS Independents")
        title_game = same_conf & (raw["week"] == final_week - 1) & ~raw["conferenceGame"].astype(bool)
        # CFBD flags some title games as conference games, so also drop a conference's only game that week.
        week_counts = raw[same_conf & (raw["week"] == final_week - 1)].groupby("homeConference")["id"].transform("size")
        lone_game = same_conf & (raw["week"] == final_week - 1) & (week_counts.reindex(raw.index).fillna(0) == 1)
        return raw[~(title_game | lone_game)][
            ["id", "seasonType", "week", "startDate", "homeTeam", "awayTeam", "neutralSite", "conferenceGame",
             "homeConference", "awayConference", "homeClassification", "awayClassification"]
        ]


def _team_rows(ctx: Context, margins: np.ndarray) -> pd.DataFrame:
    """Turn simulated margins for the remaining games into team-game rows (FBS teams only)."""
    up = ctx.upcoming
    frames = []
    for side, opp, sign, fbs_me, fbs_opp in (
        ("homeTeam", "awayTeam", 1, ctx.home_fbs, ctx.away_fbs),
        ("awayTeam", "homeTeam", -1, ctx.away_fbs, ctx.home_fbs),
    ):
        me, other = ("home", "away") if sign == 1 else ("away", "home")
        mine = fbs_me
        margin = sign * margins[mine]
        frames.append(
            pd.DataFrame(
                {
                    "game_id": up["id"][mine].to_numpy(),
                    "season_type": "regular",
                    "week": up["week"][mine].to_numpy(),
                    "start_date": up["startDate"][mine].to_numpy(),
                    "team": up[side][mine].to_numpy(),
                    "team_conference": up[f"{me}Conference"][mine].to_numpy(),
                    "opponent": up[opp][mine].to_numpy(),
                    "opponent_conference": up[f"{other}Conference"][mine].to_numpy(),
                    "opponent_is_fbs": fbs_opp[mine],
                    "neutral_site": up["neutralSite"][mine].to_numpy(bool),
                    "conference_game": up["conferenceGame"][mine].to_numpy(bool),
                    "team_pregame_elo": (ctx.home_elo if sign == 1 else ctx.away_elo)[mine],
                    "opponent_pregame_elo": np.where(fbs_opp[mine], (ctx.away_elo if sign == 1 else ctx.home_elo)[mine], np.nan),
                    "margin": margin,
                    "result": (margin > 0).astype(int),
                    "p_win": (ctx.p_home if sign == 1 else 1 - ctx.p_home)[mine],
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def simulate_once(ctx: Context, margins: np.ndarray, rng: np.random.Generator) -> pd.DataFrame:
    """One simulated finish. Returns the field (seed, team, ...) plus champion flags."""
    sim = _team_rows(ctx, margins)

    # Elo after the regular season: K * (result - expected), summed over each team's games
    elo_final = ctx.elo.copy()
    delta = (ELO_K * (sim["result"] - sim["p_win"])).groupby(sim["team"]).sum()
    elo_final = elo_final.add(delta, fill_value=0.0)

    # Conference standings -> title games between the top two of each conference
    conf_games = sim[sim["conference_game"]]
    wins = ctx.conf_wins0.add(conf_games.groupby("team")["result"].sum(), fill_value=0)
    games = ctx.conf_games0.add(conf_games.groupby("team").size(), fill_value=0)
    table = pd.DataFrame({"conference": ctx.conference, "pct": wins / games.replace(0, np.nan), "elo": elo_final}).dropna(subset=["pct"])

    title_rows, champions = [], set()
    for conf, grp in table.groupby("conference"):
        if conf == "FBS Independents" or len(grp) < 2:
            continue
        a, b = grp.sort_values(["pct", "elo"], ascending=False).index[:2]
        margin = rng.normal(MARGIN_PER_ELO * (elo_final[a] - elo_final[b]), MARGIN_SD)
        winner, loser = (a, b) if margin > 0 else (b, a)
        champions.add(winner)
        for team, opp, m in ((winner, loser, abs(margin)), (loser, winner, -abs(margin))):
            title_rows.append(
                {"game_id": -1, "season_type": "regular", "week": ctx.title_week, "start_date": f"{ctx.year}-12-05T20:00:00.000Z", "team": team,
                 "team_conference": conf, "opponent": opp, "opponent_conference": conf, "opponent_is_fbs": True,
                 "neutral_site": True, "conference_game": False, "team_pregame_elo": elo_final[team],
                 "opponent_pregame_elo": elo_final[opp], "margin": m, "result": int(m > 0)}
            )
    # Conferences with no cleanly-decided champion (e.g. fewer than 2 teams) simply have none.

    all_games = pd.concat([ctx.played, sim.drop(columns="p_win"), pd.DataFrame(title_rows)], ignore_index=True)
    # Real games keep their recorded post-game Elo; simulated games get the end-of-season rating.
    sim_mask = ~all_games["game_id"].isin(ctx.played["game_id"])
    all_games.loc[sim_mask, "team_postgame_elo"] = all_games.loc[sim_mask, "team"].map(elo_final)

    snap = snapshot(add_game_quality(all_games))
    snap["conf_champion"] = snap["team"].isin(champions).astype(int)  # trust the simulation, not the detector

    score = pd.Series(ctx.model.predict(snap[FEATURES]), index=snap.index)
    rank = (score + snap["elo_current"] * 1e-9).rank(ascending=False, method="first")
    return select_field(as_ranked_table(snap, rank), ctx.rule), champions


def run(n_sims: int, seed: int = 0, ctx: "Context | None" = None) -> pd.DataFrame:
    ctx = ctx or Context()
    rng = np.random.default_rng(seed)
    margins = rng.normal(ctx.mean_margin, MARGIN_SD, size=(n_sims, len(ctx.upcoming)))

    in_field = pd.Series(0.0, index=ctx.teams)
    bye = in_field.copy()
    champion = in_field.copy()
    seed_sum = in_field.copy()
    for i in range(n_sims):
        field, champs = simulate_once(ctx, margins[i], rng)
        in_field[field["team"]] += 1
        bye[field.loc[field["seed"] <= 4, "team"]] += 1
        seed_sum[field["team"]] += field["seed"].to_numpy()
        for c in champs:
            if c in champion.index:
                champion[c] += 1

    wins = ctx.played.groupby("team")["result"].sum()
    losses = ctx.played.groupby("team").size() - wins
    out = pd.DataFrame(
        {
            "conference": ctx.conference,
            "record": wins.reindex(ctx.teams).astype(int).astype(str) + "-" + losses.reindex(ctx.teams).astype(int).astype(str),
            "games_left": ctx.upcoming["homeTeam"].value_counts().add(ctx.upcoming["awayTeam"].value_counts(), fill_value=0).reindex(ctx.teams).fillna(0).astype(int),
            "p_field": in_field / n_sims,
            "p_bye": bye / n_sims,
            "avg_seed_if_in": (seed_sum / in_field.replace(0, np.nan)).round(1),
            "p_conf_champion": champion / n_sims,
            "elo": ctx.elo.round(0),
        }
    )
    out.index.name = "team"
    out["n_sims"] = n_sims
    return out.sort_values(["p_field", "p_bye"], ascending=False).reset_index()


START = "<!-- SIMULATION:START -->"
END = "<!-- SIMULATION:END -->"


def render_block(result: pd.DataFrame, updated: str) -> str:
    n = int(result["n_sims"].iloc[0])
    shown = result[result["p_field"] >= 0.01]
    lines = [
        START,
        f"*{n:,} simulations of the rest of the regular season and the conference title games, updated {updated}.*",
        "",
        "| Team | Record | Games left | Makes the field | First-round bye | Wins conference |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in shown.itertuples():
        lines.append(f"| {r.team} | {r.record} | {r.games_left} | {r.p_field:.0%} | {r.p_bye:.0%} | {r.p_conf_champion:.0%} |")
    lines += [
        "",
        "These capture game-to-game luck only; they assume the model's ranking is what the committee will do.",
        "In backtests they were accurate at the extremes and mildly overconfident in the middle (see below).",
        END,
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sims", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--readme", action="store_true", help="also update the README section")
    args = parser.parse_args()
    result = run(args.sims, args.seed)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(RESULT_DIR / "simulation_2026.csv", index=False)
    if args.readme:
        from datetime import datetime, timezone

        updated = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        README.write_text(replace_block(README.read_text(encoding="utf-8"), render_block(result, updated), START, END), encoding="utf-8")
    show = result.head(20).copy()
    for col in ("p_field", "p_bye", "p_conf_champion"):
        show[col] = (show[col] * 100).round(0).astype(int).astype(str) + "%"
    print(show[["team", "conference", "record", "games_left", "p_field", "p_bye", "p_conf_champion", "avg_seed_if_in"]].to_string(index=False))


if __name__ == "__main__":
    main()
