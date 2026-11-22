"""Build one row per (season, ranking week, team): that team's resume as of that moment.

Design rules
- NO LEAKAGE: a ranking labeled "week W" is released after week W-1's games, so only
  regular-season games from weeks <= W-1 are used. Postseason games are never used.
- RESUME ONLY: features come from game results and Elo ratings. Human polls (AP, Coaches)
  are kept as `ref_*` columns for comparison but must not be used as model inputs.
- NO TEAM NAMES as inputs: the model should learn how the committee turns a resume into
  a ranking, not "Alabama is usually good".

Writes data/features/features_<year>.csv

Usage:
    python -m src.features --years 2014-2026
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtr

ROOT = Path(__file__).resolve().parent.parent
CLEAN_DIR = ROOT / "data" / "clean"
FEATURE_DIR = ROOT / "data" / "features"

COMMITTEE = "Playoff Committee Rankings"

# FCS opponents have no Elo in the data; give them a fixed, clearly-below-average rating.
FCS_ELO = 1250.0

# Game model fitted on 2021-2025 FBS-vs-FBS games: margin ~ Normal(0.0417*EloDiff + 3.42*home, 16.39).
# Shared by the simulator and the strength-of-record feature so they cannot drift apart.
MARGIN_PER_ELO = 0.0417
HOME_MARGIN = 3.42
MARGIN_SD = 16.39
UNRANKED_IN_LIST = 40.0  # "not in the committee's top 25" when a list exists
MARGIN_CAP = 28 # a 50-point blowout shouldn't count much more than a 28-point one
QUALITY_PCT = 0.80  # opponent in the top 20% of that week's Elo = a "quality" opponent
BAD_PCT = 0.50  # losing to an opponent below the median = a "bad" loss

# Games played after the committee's final list but still before the label's week.
# 2019: Army-Navy (Dec 14) shares CFBD week 15 with the conference championships.
TITLE_GAME_EARLIEST = 1129  # month*100+day; conference title games are played after Thanksgiving weekend
DATE_CUTOFFS = {(2019, 16): "2019-12-08"}


def add_game_quality(games: pd.DataFrame) -> pd.DataFrame:
    """Add Elo-based opponent quality columns to the team-game table."""
    g = games.copy()
    g["opp_elo"] = g["opponent_pregame_elo"].where(g["opponent_is_fbs"], FCS_ELO)
    g["opp_elo"] = g["opp_elo"].fillna(FCS_ELO)

    # Percentile of this opponent's Elo among every FBS team playing that same week.
    def pct(week_df: pd.DataFrame) -> pd.Series:
        ref = np.sort(week_df["team_pregame_elo"].dropna().to_numpy())
        if len(ref) == 0:
            return pd.Series(np.nan, index=week_df.index)
        return pd.Series(np.searchsorted(ref, week_df["opp_elo"]) / len(ref), index=week_df.index)

    g["opp_pct"] = g.groupby("week", group_keys=False)[["team_pregame_elo", "opp_elo"]].apply(pct)
    g["margin_capped"] = g["margin"].clip(-MARGIN_CAP, MARGIN_CAP)
    g["quality_opp"] = g["opp_pct"] >= QUALITY_PCT
    g["bad_opp"] = g["opp_pct"] < BAD_PCT
    g["win"] = g["result"] == 1
    g["loss"] = ~g["win"]
    return g


def pick_champions(games: pd.DataFrame, out: pd.DataFrame) -> pd.Series:
    """Flag one champion per conference: best conference record, then head-to-head.

    Among teams tied on record we count wins over each other, then take the most recent
    head-to-head win (the title game is the latest meeting), then Elo. Before the title
    games are played this is simply the current conference leader.
    """
    champion = pd.Series(0, index=out.index)
    conf_games = games[games["conference_game"] & games["win"]]

    # A title game is the ONLY game a conference plays in its final weekend (only the two
    # finalists play). CFBD's conference_game flag is inconsistent for title games, so we
    # detect them by structure instead: same-conference matchups late in the season, taking
    # each conference's last week and keeping it only if it contains exactly one game.
    local_date = pd.to_datetime(games["start_date"], utc=True).dt.tz_convert("US/Eastern").dt.tz_localize(None)
    late = games[
        games["opponent_is_fbs"]
        & (games["team_conference"] == games["opponent_conference"])
        & (games["team_conference"] != "FBS Independents")
        & (local_date.dt.month * 100 + local_date.dt.day >= TITLE_GAME_EARLIEST)
        & (local_date.dt.month * 100 + local_date.dt.day <= 1231)
    ]
    title_winner = {}
    for conf, grp in late.groupby("team_conference"):
        last_week = grp[grp["week"] == grp["week"].max()]
        winners = last_week[last_week["win"]]
        if len(winners) == 1:  # one game = one winner row (each game appears once per team)
            title_winner[conf] = winners["team"].iloc[0]
    title_winner = pd.Series(title_winner, dtype="object")

    for conf, grp in out.groupby("conference"):
        if conf in title_winner.index and title_winner[conf] in grp.index:
            champion.loc[title_winner[conf]] = 1
            continue
        grp = grp[grp["conf_win_pct"].notna()]
        if grp.empty or conf == "FBS Independents":
            continue
        tied = grp[grp["conf_win_pct"] == grp["conf_win_pct"].max()]
        if len(tied) > 1:
            names = set(tied.index)  # `out` is indexed by team name here
            h2h = conf_games[conf_games["team"].isin(names) & conf_games["opponent"].isin(names)]
            tied = tied.assign(
                h2h_wins=tied.index.map(h2h.groupby("team").size()).fillna(0),
                h2h_last=tied.index.map(h2h.groupby("team")["start_date"].max()).fillna(""),
            ).sort_values(["h2h_wins", "h2h_last", "elo_current"], ascending=False)
        champion.loc[tied.index[0]] = 1
    return champion


def snapshot(games: pd.DataFrame) -> pd.DataFrame:
    """Aggregate each team's games (already filtered to the cutoff) into resume features."""
    games = games.sort_values(["team", "week", "start_date"])
    by = games.groupby("team")

    # Hindsight opponent quality: judge each opponent by their rating NOW (end of the
    # cutoff), the way a committee would, not by their rating on the day of the game.
    elo_now = by["team_postgame_elo"].apply(lambda s: s.dropna().iloc[-1] if s.notna().any() else np.nan)
    games = games.assign(opp_now=games["opponent"].map(elo_now).fillna(FCS_ELO))
    ref_now = np.sort(elo_now.dropna().to_numpy())
    games = games.assign(opp_now_pct=np.searchsorted(ref_now, games["opp_now"]) / max(len(ref_now), 1))
    games = games.assign(
        quality_now=games["opp_now_pct"] >= QUALITY_PCT,
        bad_now=games["opp_now_pct"] < BAD_PCT,
    )
    # Strength of record: how many wins a top-25-caliber team would be expected to have against
    # THIS schedule (home/away included), so we can see how far above that a team really is.
    ref_elo = ref_now[-25] if len(ref_now) >= 25 else np.median(ref_now)
    loc = np.where(games["neutral_site"].astype(bool), 0.0, np.where(games["is_home"], 1.0, -1.0))
    games = games.assign(p_ref=ndtr((MARGIN_PER_ELO * (ref_elo - games["opp_now"]) + HOME_MARGIN * loc) / MARGIN_SD))
    by = games.groupby("team")

    out = pd.DataFrame(
        {
            "games": by.size(),
            "wins": by["win"].sum(),
            "losses": by["loss"].sum(),
            "fbs_wins": games[games["opponent_is_fbs"]].groupby("team")["win"].sum(),
            "fbs_losses": games[games["opponent_is_fbs"]].groupby("team")["loss"].sum(),
            "avg_margin": by["margin_capped"].mean(),
            "sos": by["opp_elo"].mean(),
            "quality_wins": games[games["win"] & games["quality_opp"]].groupby("team").size(),
            "quality_losses": games[games["loss"] & games["quality_opp"]].groupby("team").size(),
            "bad_losses": games[games["loss"] & games["bad_opp"]].groupby("team").size(),
            "best_win_elo": games[games["win"]].groupby("team")["opp_elo"].max(),
            "worst_loss_elo": games[games["loss"]].groupby("team")["opp_elo"].min(),
            "conf_wins": games[games["conference_game"] & games["win"]].groupby("team").size(),
            "conf_losses": games[games["conference_game"] & games["loss"]].groupby("team").size(),
            "sos_now": by["opp_now"].mean(),
            "quality_wins_now": games[games["win"] & games["quality_now"]].groupby("team").size(),
            "bad_losses_now": games[games["loss"] & games["bad_now"]].groupby("team").size(),
            "win_value": games[games["win"]].groupby("team")["opp_now_pct"].sum(),
            "loss_cost": (1 - games[games["loss"]]["opp_now_pct"]).groupby(games["team"]).sum(),
            "best_win_now": games[games["win"]].groupby("team")["opp_now"].max(),
            "worst_loss_now": games[games["loss"]].groupby("team")["opp_now"].min(),
            "last3_wins": by["win"].apply(lambda s: s.tail(3).sum()),
            "elo_current": by["team_postgame_elo"].apply(lambda s: s.dropna().iloc[-1] if s.notna().any() else np.nan),
            "conference": by["team_conference"].last(),
        }
    )
    out[["conf_wins", "conf_losses"]] = out[["conf_wins", "conf_losses"]].fillna(0).astype(int)
    conf_games = out["conf_wins"] + out["conf_losses"]
    out["conf_win_pct"] = (out["conf_wins"] / conf_games).where(conf_games > 0)
    # Leads (or shares the lead of) its conference. After the title games this is the champion.
    best_in_conf = out.groupby("conference")["conf_win_pct"].transform("max")
    out["conf_leader"] = ((out["conf_win_pct"] == best_in_conf) & (conf_games > 0)).astype(int)
    # How strong is this team's whole conference right now? Data-driven (average Elo), not a list
    # of conference names, so it also handles realignment (e.g. the rebuilt 2026 Pac-12).
    out["conf_strength"] = out.groupby("conference")["elo_current"].transform("mean")
    # Independents are not a conference (2-3 unrelated teams): give them the FBS-wide average.
    out.loc[out["conference"] == "FBS Independents", "conf_strength"] = out["elo_current"].mean()
    out["elo_vs_conf"] = out["elo_current"] - out["conf_strength"]
    out["conf_champion"] = pick_champions(games, out)
    out[["win_value", "loss_cost"]] = out[["win_value", "loss_cost"]].fillna(0.0)
    count_cols = ["fbs_wins", "fbs_losses", "quality_wins", "quality_losses", "bad_losses",
                  "quality_wins_now", "bad_losses_now"]
    out[count_cols] = out[count_cols].fillna(0).astype(int)
    out["wins"] = out["wins"].astype(int)
    out["losses"] = out["losses"].astype(int)
    out["win_pct"] = out["wins"] / out["games"]
    expected_wins_ref = by["p_ref"].sum()
    out["wins_above_ref"] = out["wins"] - expected_wins_ref
    out["ref_expected_losses"] = out["games"] - expected_wins_ref
    out["undefeated"] = (out["losses"] == 0).astype(int)
    return out.reset_index()


def ranking_weeks(year: int, ranks: pd.DataFrame, games: pd.DataFrame, in_progress: bool) -> list[int]:
    """Which ranking weeks to build snapshots for.

    Finished seasons: the committee's weeks. A season in progress also gets a "right now"
    snapshot (every game played so far), because the committee's latest list always trails the
    most recent results by about a week.
    """
    committee = ranks[(ranks["poll"] == COMMITTEE) & (ranks["season_type"] == "regular")]
    weeks = set(committee["week"])
    if not weeks:
        weeks = set(ranks.loc[ranks["poll"] == "AP Top 25", "week"]) - {1}
    if in_progress:
        played = games[games["season_type"] == "regular"]["week"]
        weeks.add(int(played.max()) + 1)
    return sorted(weeks)


def build_year(year: int) -> pd.DataFrame:
    games = add_game_quality(pd.read_csv(CLEAN_DIR / f"team_games_{year}.csv"))
    ranks = pd.read_csv(CLEAN_DIR / f"rankings_{year}.csv").rename(columns={"seasonType": "season_type"})
    regular = games[games["season_type"] == "regular"]
    # No postseason games played yet means the season is still going.
    in_progress = not (games["season_type"] == "postseason").any()

    frames = []
    for week in ranking_weeks(year, ranks, games, in_progress):
        cutoff = regular[regular["week"] <= week - 1]
        if (year, week) in DATE_CUTOFFS:
            cutoff = cutoff[cutoff["start_date"].str[:10] < DATE_CUTOFFS[(year, week)]]
        if cutoff.empty:
            continue

        snap = snapshot(cutoff)
        snap.insert(0, "ranking_week", week)
        snap.insert(0, "season", year)

        regular_ranks = ranks[ranks["season_type"] == "regular"]
        for poll, col in [(COMMITTEE, "committee_rank"), ("AP Top 25", "ref_ap_rank"), ("Coaches Poll", "ref_coaches_rank")]:
            poll_df = regular_ranks[regular_ranks["poll"] == poll]
            if poll == COMMITTEE:
                poll_df = poll_df[poll_df["week"] == week]  # labels must match this exact week
            else:
                # Reference polls: use the latest poll out by this week (the current week's may not exist yet).
                available = poll_df[poll_df["week"] <= week]["week"]
                poll_df = poll_df[poll_df["week"] == available.max()] if not available.empty else poll_df.iloc[0:0]
            snap[col] = snap["team"].map(poll_df.set_index("school")["rank"])

        # The committee's most recent list released BEFORE this one. It is sticky: teams move a few
        # spots at a time, so the last list is a strong clue to the next. Strictly earlier weeks only.
        earlier = sorted(w for w in set(regular_ranks.loc[regular_ranks["poll"] == COMMITTEE, "week"]) if w < week)
        if earlier:
            last = regular_ranks[(regular_ranks["poll"] == COMMITTEE) & (regular_ranks["week"] == earlier[-1])]
            snap["last_list_rank"] = snap["team"].map(last.set_index("school")["rank"]).fillna(UNRANKED_IN_LIST)
            snap["last_list_week"] = earlier[-1]
        else:
            snap["last_list_rank"] = np.nan  # no list has been published yet (first list of the year)
            snap["last_list_week"] = np.nan
        frames.append(snap)

    result = pd.concat(frames, ignore_index=True)
    result["season_complete"] = int(not in_progress)
    result["in_committee_top12"] = (result["committee_rank"] <= 12).astype(int)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--years", help="Inclusive range such as 2014-2026")
    args = parser.parse_args()
    if args.years:
        first, last = (int(y) for y in args.years.split("-"))
        years = range(first, last + 1)
    else:
        years = [args.year]

    FEATURE_DIR.mkdir(parents=True, exist_ok=True)
    for year in years:
        df = build_year(year)
        df.to_csv(FEATURE_DIR / f"features_{year}.csv", index=False)
        labeled = df["committee_rank"].notna().sum()
        print(f"{year}: {len(df)} rows, {df['ranking_week'].nunique()} ranking weeks, {labeled} committee-labeled")


if __name__ == "__main__":
    main()
