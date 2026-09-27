#!/usr/bin/env python3
"""Update data/stats.json.

Regular season: ESPN season stats (Basketball-Reference as a fallback).
Playoffs: ESPN scoreboard + box scores, stored game by game so the page can
group them by series and round.

Usage:
    python scripts/fetch_stats.py                 # current season
    python scripts/fetch_stats.py --season 2025   # a past season
    python scripts/fetch_stats.py --skip-regular  # playoffs only (faster during the playoffs)
"""
import argparse
import datetime as dt
import io
import json
import pathlib
import sys
import time

import pandas as pd
import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data" / "stats.json"
HEADERS = {"User-Agent": "wnba-stat-leaders/1.1 (personal stat tracker; GitHub Pages)"}

# ---------------------------------------------------------------- regular season (Basketball-Reference)
BREF_PER_GAME = "https://www.basketball-reference.com/wnba/years/{season}_per_game.html"
BREF_TOTALS = "https://www.basketball-reference.com/wnba/years/{season}_totals.html"
FIELDS = {
    "MP": "mp", "FG": "fg", "FGA": "fga", "FG%": "fg_pct", "3P": "fg3", "3PA": "fg3a", "3P%": "fg3_pct",
    "FT": "ft", "FTA": "fta", "FT%": "ft_pct", "TRB": "trb", "AST": "ast", "STL": "stl", "BLK": "blk",
    "TOV": "tov", "PTS": "pts",
}
PCT = {"fg_pct", "fg3_pct", "ft_pct"}
MULTI_TEAM = {"TOT", "2TM", "3TM", "4TM"}


def bref_table(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return pd.read_html(io.StringIO(r.text))[0]


def bref_rows(df):
    """Return {player name: {team, pos, g, stats{...}}} from a per-game or totals table."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[-1] for c in df.columns]
    cols = [str(c).strip() for c in df.columns]

    def col(name, last=True):
        idx = [i for i, c in enumerate(cols) if c == name]
        if not idx:
            return None
        return df.iloc[:, idx[-1] if last else idx[0]]

    player, team, pos, games = col("Player"), col("Team"), col("Pos"), col("G", last=False)
    if team is None:
        team = col("Tm")
    rows = {}
    for i in range(len(df)):
        name = str(player.iloc[i]).strip().rstrip("*")
        if name in ("Player", "League Average", "nan", ""):
            continue
        t = str(team.iloc[i]).strip() if team is not None else ""
        g = pd.to_numeric(games.iloc[i], errors="coerce") if games is not None else None
        stats = {}
        for src, dst in FIELDS.items():
            s = col(src)
            v = pd.to_numeric(s.iloc[i], errors="coerce") if s is not None else None
            stats[dst] = None if v is None or pd.isna(v) else float(v)
        rec = {"team": t, "pos": str(pos.iloc[i]).strip() if pos is not None else "",
               "g": None if g is None or pd.isna(g) else int(g), "stats": stats, "teams": [t]}
        if name in rows:  # traded player: keep the combined row, collect every team
            prev = rows[name]
            teams = [x for x in prev["teams"] + [t] if x not in MULTI_TEAM]
            if t in MULTI_TEAM:
                rows[name] = rec
            rows[name]["teams"] = teams
        else:
            rows[name] = rec
    for rec in rows.values():
        teams = [x for x in rec["teams"] if x not in MULTI_TEAM]
        if rec["team"] in MULTI_TEAM and teams:
            rec["team"] = "/".join(dict.fromkeys(teams))
    return rows


def fetch_regular(season):
    pg = bref_table(BREF_PER_GAME.format(season=season))
    if pg is None:
        return None
    per_game = bref_rows(pg)
    time.sleep(4)
    try:
        tt = bref_table(BREF_TOTALS.format(season=season))
        totals = bref_rows(tt) if tt is not None else {}
    except Exception as e:
        print(f"Totals table failed ({e}); totals will be estimated from per-game x games", file=sys.stderr)
        totals = {}
    players = []
    for name, rec in per_game.items():
        if not rec["g"]:
            continue
        pgs = rec["stats"]
        if name in totals:
            tot = dict(totals[name]["stats"])
        else:
            tot = {k: (None if v is None else round(v * rec["g"])) for k, v in pgs.items()}
        for k in PCT:
            tot[k] = pgs.get(k)
        players.append({"name": name, "team": rec["team"], "pos": rec["pos"], "g": rec["g"], "pg": pgs, "tot": tot})
    return {"label": "Regular Season", "source_name": "Basketball-Reference.com",
            "url": BREF_PER_GAME.format(season=season), "players": players}


# ---------------------------------------------------------------- regular season (ESPN, primary)
ESPN_SEASON = ("https://site.web.api.espn.com/apis/common/v3/sports/basketball/wnba/statistics/byathlete"
               "?region=us&lang=en&contentorigin=espn&isqualified=false&limit=1000&season={season}&seasontype=2"
               "&sort=offensive.avgPoints:desc")
ESPN_FIELDS = {  # ESPN stat name -> (our field, is_percent)
    "avgMinutes": ("mp", False), "avgRebounds": ("trb", False), "avgPoints": ("pts", False),
    "avgFieldGoalsMade": ("fg", False), "avgFieldGoalsAttempted": ("fga", False), "fieldGoalPct": ("fg_pct", True),
    "avgThreePointFieldGoalsMade": ("fg3", False), "avgThreePointFieldGoalsAttempted": ("fg3a", False),
    "threePointFieldGoalPct": ("fg3_pct", True), "avgFreeThrowsMade": ("ft", False),
    "avgFreeThrowsAttempted": ("fta", False), "freeThrowPct": ("ft_pct", True), "avgAssists": ("ast", False),
    "avgTurnovers": ("tov", False), "avgSteals": ("stl", False), "avgBlocks": ("blk", False),
}


def fetch_regular_espn(season):
    data = get_json(ESPN_SEASON.format(season=season))
    names = {c["name"]: c.get("names") or c.get("labels") or [] for c in data.get("categories", [])}
    players = []
    for a in data.get("athletes", []):
        ath = a.get("athlete", {})
        vals = {}
        for cat in a.get("categories", []):
            for n, v in zip(names.get(cat["name"], []), cat.get("values") or cat.get("totals") or []):
                vals[n] = v
        g = int(vals.get("gamesPlayed") or 0)
        if not g:
            continue
        pg = {}
        for src, (dst, is_pct) in ESPN_FIELDS.items():
            v = vals.get(src)
            try:
                v = None if v is None else float(v)
            except (TypeError, ValueError):
                v = None
            pg[dst] = None if v is None else round(v / 100, 4) if is_pct else round(v, 2)
        tot = {k: (None if v is None else round(v * g)) for k, v in pg.items()}
        for k in PCT:
            tot[k] = pg.get(k)
        if vals.get("points") is not None:
            tot["pts"] = int(float(vals["points"]))
        team = (ath.get("teamShortName") or (ath.get("team") or {}).get("abbreviation")
                or ((ath.get("teams") or [{}])[-1]).get("abbreviation") or "")
        players.append({"name": ath.get("displayName", ""), "team": code(team),
                        "pos": (ath.get("position") or {}).get("abbreviation", ""), "g": g, "pg": pg, "tot": tot})
    if not players:
        return None
    return {"label": "Regular Season", "source_name": "ESPN",
            "url": f"https://www.espn.com/wnba/stats/player/_/season/{season}/seasontype/2", "players": players}


# ---------------------------------------------------------------- playoffs (ESPN)
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard?dates={day}"
ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/summary?event={id}"
# ESPN abbreviations -> the codes the page uses
TEAM_CODE = {"LV": "LVA", "NY": "NYL", "GS": "GSV", "CONN": "CON", "LA": "LAS", "PHX": "PHO", "WSH": "WAS"}
ROUND_NAMES = {1: "First Round", 2: "Semifinals", 3: "Finals"}


def code(abbr):
    return TEAM_CODE.get(abbr, abbr)


def get_json(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def split_made(v):
    try:
        m, a = str(v).split("-")
        return int(m), int(a)
    except ValueError:
        return 0, 0


def to_int(v):
    try:
        return int(float(str(v).split(":")[0]))
    except ValueError:
        return 0


def box_lines(game_id):
    data = get_json(ESPN_SUMMARY.format(id=game_id))
    lines = []
    for team in data.get("boxscore", {}).get("players", []):
        t = code(team["team"]["abbreviation"])
        for block in team.get("statistics", []):
            keys = block.get("keys", [])
            for a in block.get("athletes", []):
                if a.get("didNotPlay") or not a.get("stats"):
                    continue
                s = dict(zip(keys, a["stats"]))
                fgm, fga = split_made(s.get("fieldGoalsMade-fieldGoalsAttempted", "0-0"))
                tpm, tpa = split_made(s.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted", "0-0"))
                ftm, fta = split_made(s.get("freeThrowsMade-freeThrowsAttempted", "0-0"))
                lines.append({
                    "g": game_id, "t": t, "n": a["athlete"]["displayName"], "st": bool(a.get("starter")),
                    "min": to_int(s.get("minutes", 0)), "pts": to_int(s.get("points", 0)),
                    "trb": to_int(s.get("rebounds", 0)), "ast": to_int(s.get("assists", 0)),
                    "stl": to_int(s.get("steals", 0)), "blk": to_int(s.get("blocks", 0)),
                    "tov": to_int(s.get("turnovers", 0)),
                    "fg": fgm, "fga": fga, "fg3": tpm, "fg3a": tpa, "ft": ftm, "fta": fta,
                })
    return lines


def fetch_playoffs(season, existing):
    """Scan the playoff window day by day, keep finished box scores we already have."""
    have = {ln["g"] for ln in existing.get("lines", [])}
    old_games = {g["id"]: g for g in existing.get("games", [])}
    start = dt.date(season, 9, 1)
    end = min(dt.date(season, 11, 10), dt.date.today() + dt.timedelta(days=10))
    games = {}
    day = start
    while day <= end:
        try:
            sb = get_json(ESPN_SCOREBOARD.format(day=day.strftime("%Y%m%d")))
        except Exception as e:
            print(f"Scoreboard {day} failed ({e})", file=sys.stderr)
            sb = {"events": []}
        for ev in sb.get("events", []):
            if ev.get("season", {}).get("type") != 3:
                continue
            comp = ev["competitions"][0]
            teams = {c["homeAway"]: c for c in comp["competitors"]}
            abbrs = [teams.get(k, {}).get("team", {}).get("abbreviation", "") for k in ("home", "away")]
            if any(not a or a.upper() in ("TBD", "TBA") for a in abbrs):
                continue  # future round, teams not decided yet
            note = next((n.get("headline", "") for n in comp.get("notes", []) if n.get("headline")), "")
            games[ev["id"]] = {
                "id": ev["id"], "date": ev["date"], "note": note,
                "home": code(teams["home"]["team"]["abbreviation"]),
                "away": code(teams["away"]["team"]["abbreviation"]),
                "hs": to_int(teams["home"].get("score", 0)), "as": to_int(teams["away"].get("score", 0)),
                "final": bool(ev["status"]["type"].get("completed")),
            }
        day += dt.timedelta(days=1)
        time.sleep(0.25)

    if not games:  # ESPN unreachable or no playoff games yet: keep what we had
        return existing or None

    # Round = how many different opponents a team has faced so far (works for any bracket).
    by_team = {}
    for g in sorted(games.values(), key=lambda g: g["date"]):
        for t, opp in ((g["home"], g["away"]), (g["away"], g["home"])):
            seen = by_team.setdefault(t, [])
            if not seen or seen[-1] != opp:
                seen.append(opp)
            if t == g["home"]:
                g["round"] = len(seen)
    series = {}
    for g in games.values():
        a, b = sorted([g["home"], g["away"]])
        sid = f"R{g['round']}-{a}-{b}"
        g["series"] = sid
        s = series.setdefault(sid, {"id": sid, "round": g["round"], "teams": [a, b], "wins": {a: 0, b: 0},
                                    "name": ROUND_NAMES.get(g["round"], f"Round {g['round']}")})
        if g["note"] and " - " in g["note"]:
            s["name"] = g["note"].split(" - ")[0].replace("WNBA ", "").strip() or s["name"]
        if g["final"]:
            winner = g["home"] if g["hs"] > g["as"] else g["away"]
            s["wins"][winner] += 1

    lines = [ln for ln in existing.get("lines", []) if ln["g"] in games and games[ln["g"]]["final"]]
    for gid, g in games.items():
        if not g["final"] or (gid in have and old_games.get(gid, {}).get("final")):
            continue
        try:
            lines.extend(box_lines(gid))
            print(f"Box score {g['away']} @ {g['home']} ({gid})", file=sys.stderr)
        except Exception as e:
            print(f"Box score {gid} failed ({e})", file=sys.stderr)
        time.sleep(0.5)

    return {
        "label": "Playoffs",
        "url": "https://www.espn.com/wnba/scoreboard",
        "games": sorted(games.values(), key=lambda g: g["date"]),
        "series": sorted(series.values(), key=lambda s: (s["round"], s["id"])),
        "lines": lines,
    }


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=dt.date.today().year)
    ap.add_argument("--skip-regular", action="store_true")
    args = ap.parse_args()

    existing = {}
    if OUT.exists():
        try:
            existing = json.loads(OUT.read_text())
            if existing.get("season") != args.season:
                existing = {}
        except json.JSONDecodeError:
            existing = {}

    result = {
        "season": args.season,
        "updated": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "preview": False,
        "source": "ESPN",
        "regular": existing.get("regular"),
        "playoffs": existing.get("playoffs"),
    }

    if not args.skip_regular:
        reg = None
        for name, fn in (("ESPN", fetch_regular_espn), ("Basketball-Reference", fetch_regular)):
            try:
                reg = fn(args.season)
            except Exception as e:
                print(f"Regular season from {name} failed ({e})", file=sys.stderr)
                reg = None
            if reg and reg["players"]:
                print(f"Regular season: {len(reg['players'])} players from {name}", file=sys.stderr)
                break
            print(f"Regular season from {name}: no data", file=sys.stderr)
        if reg and reg["players"]:
            result["regular"] = reg
        else:
            print("Regular season: keeping previous data", file=sys.stderr)

    try:
        po = fetch_playoffs(args.season, existing.get("playoffs") or {})
        if po:
            result["playoffs"] = po
            print(f"Playoffs: {len(po['games'])} games, {len(po['lines'])} player lines", file=sys.stderr)
    except Exception as e:
        print(f"Playoffs failed ({e}); keeping previous data", file=sys.stderr)

    if not result["regular"] and not result["playoffs"]:
        sys.exit("Nothing pulled; leaving the existing stats.json in place.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False))
    print(f"Wrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
