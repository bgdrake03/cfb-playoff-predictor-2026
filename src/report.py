"""Refresh the 'current prediction' section of README.md from data/results/prediction_2026.csv.

The README holds a block between two marker comments; this script replaces only that block.

Usage:
    python -m src.report
"""
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
PREDICTION = ROOT / "data" / "results" / "prediction_2026.csv"
HISTORY = ROOT / "data" / "results" / "history"

START = "<!-- PREDICTION:START -->"
END = "<!-- PREDICTION:END -->"


def render_block(field: pd.DataFrame, week: int, updated: str, why: str = "") -> str:
    """Markdown for the prediction section, including the markers."""
    lines = [
        START,
        f"*Updated {updated} · ranking week {week} · champions are projected from current standings until title games are played.*",
        "",
        "| Seed | Team | Conference | Record | Why they're in |",
        "|---:|---|---|---|---|",
    ]
    for r in field.itertuples():
        lines.append(f"| {r.seed} | {r.team} | {r.conference} | {r.record} | {r.reason} |")
    lines += [
        "",
        "Seeds 1–4 get first-round byes. 2026 seeding is assumed to follow the ranking (see Limitations).",
    ]
    if why:
        lines += ["", why]
    lines.append(END)
    return "\n".join(lines)


def replace_block(readme: str, block: str, start: str = START, end: str = END) -> str:
    """Replace everything between two marker comments (inclusive) with `block`."""
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if not pattern.search(readme):
        raise ValueError(f"README is missing the {start} ... {end} markers")
    return pattern.sub(lambda _: block, readme, count=1)


def latest_week() -> int:
    weeks = [int(p.stem.rsplit("week", 1)[1]) for p in HISTORY.glob("prediction_2026_week*.csv")]
    return max(weeks)


def main() -> None:
    from src.explain import field_why, team_table
    from src.model import load_features

    field = pd.read_csv(PREDICTION)
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Plain-English "why" text, built from the same snapshot the prediction used.
    df = load_features()
    season = df[df["season_complete"] == 0]
    snap = season[season["ranking_week"] == season["ranking_week"].max()]
    games = pd.read_csv(ROOT / "data" / "clean" / f"team_games_{int(snap['season'].iloc[0])}.csv")
    ranking = pd.read_csv(ROOT / "data" / "results" / "ranking_2026.csv")
    why = field_why(field, ranking, team_table(snap, games))
    block = render_block(field, latest_week(), updated, why)
    README.write_text(replace_block(README.read_text(encoding="utf-8"), block), encoding="utf-8")
    print(f"README updated with {len(field)} teams (week {latest_week()})")


if __name__ == "__main__":
    main()
