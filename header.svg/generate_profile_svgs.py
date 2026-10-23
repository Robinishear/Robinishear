#!/usr/bin/env python3
"""Generates assets/stats.svg and assets/activity.svg for a GitHub profile README.

Env:
  GITHUB_USERNAME   GitHub login (default: repository owner)
  GITHUB_TOKEN      token used for API calls (the Action's built-in token works)
  GH_STATS_PRIVATE  set to "1" when GITHUB_TOKEN is a personal access token (repo scope)
                    so private repositories are counted too
"""
import json, math, os, random, sys, urllib.request, urllib.error
from datetime import datetime, timezone

USER = os.environ.get("GITHUB_USERNAME") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "Robinishear"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
PRIVATE = os.environ.get("GH_STATS_PRIVATE") == "1" and bool(TOKEN)
OUT = os.environ.get("OUT_DIR", "assets")
MONO = "'JetBrains Mono','Fira Code',Consolas,Menlo,monospace"
SANS = "Inter,'Segoe UI','Helvetica Neue',Arial,sans-serif"
NOW = datetime.now(timezone.utc)


def esc(t):
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def api(path, data=None):
    url = path if path.startswith("http") else "https://api.github.com" + path
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-svg-generator"}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print(f"[warn] {path}: {e}", file=sys.stderr)
        return None


def paginate(path):
    out, page = [], 1
    while True:
        sep = "&" if "?" in path else "?"
        chunk = api(f"{path}{sep}per_page=100&page={page}")
        if not chunk:
            break
        out += chunk
        if len(chunk) < 100:
            break
        page += 1
    return out


# ------------------------------------------------------------------ data
def collect():
    d = {"repos": None, "stars": None, "followers": None, "commits": None, "prs": None,
         "streak": None, "longest": None, "langs": [], "weeks": [], "total": None}
    u = api(f"/users/{USER}") or {}
    d["followers"] = u.get("followers")
    if PRIVATE:
        repos = paginate("/user/repos?affiliation=owner&visibility=all")
    else:
        repos = paginate(f"/users/{USER}/repos?type=owner")
    mine = [r for r in repos if not r.get("fork")]
    d["repos"] = len(repos) if repos else u.get("public_repos")
    d["stars"] = sum(r.get("stargazers_count", 0) for r in mine)

    # languages (bytes). Fall back to each repo's main language if the API is rate limited.
    totals, limit = {}, 100 if TOKEN else 25
    for r in sorted(mine, key=lambda r: r.get("pushed_at") or "", reverse=True)[:limit]:
        langs = api(f"/repos/{r['full_name']}/languages")
        if langs:
            for k, v in langs.items():
                totals[k] = totals.get(k, 0) + v
    if not totals:
        for r in mine:
            if r.get("language"):
                totals[r["language"]] = totals.get(r["language"], 0) + max(r.get("size", 1), 1)
    s = sum(totals.values()) or 1
    d["langs"] = [(k, v / s) for k, v in sorted(totals.items(), key=lambda kv: -kv[1])[:6]]

    # contributions (needs a token)
    if TOKEN:
        q = """query($login:String!){user(login:$login){contributionsCollection{
          totalCommitContributions totalPullRequestContributions
          contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
        res = api("https://api.github.com/graphql", {"query": q, "variables": {"login": USER}})
        try:
            cc = res["data"]["user"]["contributionsCollection"]
            d["commits"] = cc["totalCommitContributions"]
            d["prs"] = cc["totalPullRequestContributions"]
            d["total"] = cc["contributionCalendar"]["totalContributions"]
            weeks = cc["contributionCalendar"]["weeks"]
            days = [x for w in weeks for x in w["contributionDays"]]
            d["weeks"] = [sum(x["contributionCount"] for x in w["contributionDays"]) for w in weeks][-26:]
            cur = best = run = 0
            for x in days:
                if x["contributionCount"] > 0:
                    run += 1; best = max(best, run)
                else:
                    run = 0
            for x in reversed(days):
                if x["contributionCount"] > 0:
                    cur += 1
                elif x is days[-1]:
                    continue  # today may still be empty
                else:
                    break
            d["streak"], d["longest"] = cur, best
        except (TypeError, KeyError):
            print("[warn] GraphQL contributions unavailable", file=sys.stderr)
    return d


LANG_COLORS = {"TypeScript": "#3178C6", "JavaScript": "#F7DF1E", "Python": "#3776AB", "Go": "#00ADD8",
               "HTML": "#E34F26", "CSS": "#1572B6", "Shell": "#89e051", "Dockerfile": "#2496ED",
               "SCSS": "#c6538c", "PLpgSQL": "#336791", "Dart": "#00B4AB", "Kotlin": "#A97BFF",
               "Java": "#b07219", "C++": "#f34b7d", "C": "#9aa0a6", "Rust": "#dea584", "Vue": "#41b883",
               "Solidity": "#94a3b8", "Makefile": "#6d8086", "EJS": "#a91e50"}
FALLBACK = ["#34d399", "#B48CFF", "#FFB84D", "#f472b6", "#60a5fa", "#fb923c"]


# ------------------------------------------------------------------ svg base
def base(W, H, title, desc, tag, heading, sub, body, seed=1):
    random.seed(seed)
    parts = [f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t d">
<title id="t">{esc(title)}</title><desc id="d">{esc(desc)}</desc>
<defs>
<style>.card{{animation:up .9s cubic-bezier(.2,.7,.2,1) both}}@keyframes up{{from{{opacity:0;transform:translateY(16px)}}to{{opacity:1;transform:none}}}}@media (prefers-reduced-motion:reduce){{.card{{animation:none}}}}</style>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1b0b14"/><stop offset=".30" stop-color="#180b14"/><stop offset=".62" stop-color="#2d0b1b"/><stop offset="1" stop-color="#481027"/></linearGradient>
<linearGradient id="bf" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3b1527"/><stop offset=".22" stop-color="#87536a"/><stop offset=".36" stop-color="#d4a0b8"/><stop offset=".5" stop-color="#4a1a30"/><stop offset=".72" stop-color="#87536a"/><stop offset="1" stop-color="#351020"/><animateTransform attributeName="gradientTransform" type="rotate" from="0 .5 .5" to="360 .5 .5" dur="8s" repeatCount="indefinite"/></linearGradient>
<linearGradient id="gl" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#d4b4c1" stop-opacity=".95"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
<linearGradient id="gr" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#87536a"/><stop offset=".5" stop-color="#5f3045" stop-opacity=".4"/><stop offset="1" stop-color="#5f3045" stop-opacity="0"/></linearGradient>
<linearGradient id="tg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#B48CFF"/><stop offset=".5" stop-color="#34d399"/><stop offset="1" stop-color="#FFB84D"/></linearGradient>
<linearGradient id="sw" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#d4a0b8" stop-opacity=".07"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
<radialGradient id="vg" cx="50%" cy="48%" r="75%"><stop offset=".55" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".16"/></radialGradient>
<pattern id="dots" width="26" height="26" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.1" fill="#52525b" fill-opacity=".4"/></pattern>
<pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="#87536a" stroke-opacity=".03"/></pattern>
<filter id="orb" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="60"/></filter>
<filter id="glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<filter id="tg2" x="-20%" y="-60%" width="140%" height="220%"><feGaussianBlur stdDeviation="9"/></filter>
<clipPath id="fr"><rect x="4" y="4" width="{W-8}" height="{H-8}" rx="26"/></clipPath>
</defs>
<rect width="{W}" height="{H}" fill="#000"/>
<g clip-path="url(#fr)"><rect width="{W}" height="{H}" fill="url(#bg)"/><rect width="{W}" height="{H}" fill="url(#dots)"/><rect width="{W}" height="{H}" fill="url(#grid)"/>
<g filter="url(#orb)">
<ellipse cx="260" cy="120" rx="340" ry="170" fill="#6d28d9" opacity=".14"><animateTransform attributeName="transform" type="translate" values="0 0;60 -10;-40 20;0 0" dur="15s" repeatCount="indefinite"/></ellipse>
<ellipse cx="{W-220}" cy="120" rx="320" ry="150" fill="#9f1239" opacity=".2"><animateTransform attributeName="transform" type="translate" values="0 0;-70 20;40 30;0 0" dur="13s" repeatCount="indefinite"/></ellipse>
<ellipse cx="{W//2}" cy="{H-100}" rx="360" ry="150" fill="#10b981" opacity=".08"><animateTransform attributeName="transform" type="translate" values="0 0;50 -10;-40 10;0 0" dur="17s" repeatCount="indefinite"/></ellipse>
</g>''']
    cols = ["#a1a1aa", "#d4d4d8", "#87536a", "#34d399", "#B48CFF", "#FFB84D", "#f472b6"]
    for _ in range(22):
        x = random.randint(20, W - 20); dx = random.randint(-40, 40)
        dur = round(random.uniform(9, 15), 1); beg = -round(random.uniform(0, dur), 1)
        parts.append(f'<circle r="{random.choice([1.2,1.6,2,2.4])}" fill="{random.choice(cols)}"><animateMotion path="M{x} {H+20} L{x+dx} -20" dur="{dur}s" begin="{beg}s" repeatCount="indefinite"/><animate attributeName="opacity" values="0;.75;.75;0" keyTimes="0;.15;.8;1" dur="{dur}s" begin="{beg}s" repeatCount="indefinite"/></circle>')
    parts.append(f'''<rect x="40" y="27" width="4" height="22" rx="2" fill="#d4a0b8"><animate attributeName="opacity" values="1;.35;1" dur="2.4s" repeatCount="indefinite"/></rect>
<text x="58" y="46" font-family="{MONO}" font-size="20" font-weight="700" letter-spacing="7" fill="url(#tg)">{esc(tag)}</text>
<text font-family="{SANS}" font-style="italic" x="40" y="112" font-size="60" font-weight="800" letter-spacing="-1" fill="#87536a" opacity=".6" filter="url(#tg2)"><animate attributeName="fill" values="#f472b6;#B48CFF;#34d399;#FFB84D;#f472b6" dur="12s" repeatCount="indefinite"/>{esc(heading)}</text>
<text font-family="{SANS}" font-style="italic" x="40" y="112" font-size="60" font-weight="800" letter-spacing="-1" fill="#f6eef2">{esc(heading)}</text>
<text font-family="{SANS}" font-style="italic" x="42" y="146" font-size="21" fill="#d9c3cd">{esc(sub)}</text>
<rect x="40" y="160" width="{W-80}" height="2" rx="1" fill="url(#gr)"/><rect x="40" y="159" width="120" height="4" rx="2" fill="url(#gl)"><animate attributeName="x" values="40;{W-160};40" dur="9s" repeatCount="indefinite"/></rect>''')
    parts += body
    parts.append(f'''<g transform="skewX(-16)"><rect x="-500" y="0" width="360" height="{H}" fill="url(#sw)"><animateTransform attributeName="transform" type="translate" values="0 0;0 0;2400 0" keyTimes="0;.3;1" dur="11s" repeatCount="indefinite"/></rect></g>
<rect width="{W}" height="{H}" fill="url(#vg)"/></g>
<rect x="3" y="3" width="{W-6}" height="{H-6}" rx="27" fill="none" stroke="url(#bf)" stroke-width="3"/>
</svg>''')
    return "\n".join(parts)


def fmt(n):
    return "—" if n is None else f"{n:,}"


# ------------------------------------------------------------------ stats.svg
def stats_svg(d):
    W, H = 1600, 660
    body = []
    tiles = [("REPOSITORIES", fmt(d["repos"]), "#34d399"), ("STARS EARNED", fmt(d["stars"]), "#FFB84D"),
             ("FOLLOWERS", fmt(d["followers"]), "#f472b6"), ("COMMITS · YEAR", fmt(d["commits"]), "#B48CFF"),
             ("PRS · YEAR", fmt(d["prs"]), "#60a5fa"),
             ("CURRENT STREAK", "—" if d["streak"] is None else f'{d["streak"]} days', "#fb923c")]
    for i, (lab, val, col) in enumerate(tiles):
        r, c = divmod(i, 3)
        x, y = 48 + c * 250, 190 + r * 148
        body.append(f'''<g transform="translate({x},{y})"><g class="card" style="animation-delay:{0.3+i*0.1:.1f}s">
<rect width="232" height="130" rx="20" fill="{col}" fill-opacity=".06" stroke="{col}" stroke-opacity=".4" stroke-width="1.5"><animate attributeName="stroke-opacity" values=".35;1;1;.35;.35" keyTimes="0;.04;.16;.2;1" dur="12s" begin="{i*2}s" repeatCount="indefinite"/></rect>
<rect x="1" y="1" width="230" height="3" rx="1.5" fill="{col}" fill-opacity=".85"/>
<circle cx="30" cy="34" r="5" fill="{col}"><animate attributeName="opacity" values="1;.3;1" dur="2.4s" begin="{i*0.4:.1f}s" repeatCount="indefinite"/></circle>
<text x="46" y="39" font-family="{MONO}" font-size="12.5" font-weight="700" letter-spacing="2" fill="#c9b3be">{esc(lab)}</text>
<text x="24" y="98" font-family="{SANS}" font-style="italic" font-size="42" font-weight="800" fill="#f6eef2">{esc(val)}</text></g></g>''')
    # languages
    body.append(f'<g class="card" style="animation-delay:.5s"><rect x="820" y="190" width="732" height="278" rx="22" fill="#d4b4c1" fill-opacity=".05" stroke="#87536a" stroke-opacity=".7" stroke-width="1.5"/><text x="848" y="230" font-family="{MONO}" font-size="14" font-weight="700" letter-spacing="4" fill="#b994a4">TOP LANGUAGES</text></g>')
    langs = d["langs"] or []
    for i, (name, frac) in enumerate(langs):
        y = 262 + i * 33
        col = LANG_COLORS.get(name, FALLBACK[i % len(FALLBACK)])
        w = max(6, 380 * frac / (langs[0][1] or 1))
        body.append(f'''<g class="card" style="animation-delay:{0.7+i*0.1:.1f}s"><circle cx="856" cy="{y+7}" r="6" fill="{col}"/>
<text x="874" y="{y+13}" font-family="{SANS}" font-size="18" font-weight="600" fill="#f1e8ed">{esc(name)}</text>
<rect x="1020" y="{y}" width="400" height="14" rx="7" fill="#2a101c"/>
<rect x="1020" y="{y}" width="{w:.0f}" height="14" rx="7" fill="{col}" filter="url(#glow)"><animate attributeName="width" values="0;0;{w:.0f}" keyTimes="0;{0.3+i*0.04:.2f};1" dur="2s" fill="freeze"/></rect>
<text x="1530" y="{y+13}" text-anchor="end" font-family="{MONO}" font-size="15" font-weight="700" fill="#d9c3cd">{frac*100:.1f}%</text></g>''')
    if not langs:
        body.append(f'<text x="848" y="290" font-family="{SANS}" font-style="italic" font-size="20" fill="#cdb3bf">Language data appears after the first successful run.</text>')
    # contribution sparkline
    body.append(f'<g class="card" style="animation-delay:1s"><rect x="48" y="496" width="1504" height="130" rx="22" fill="#d4b4c1" fill-opacity=".05" stroke="#87536a" stroke-opacity=".7" stroke-width="1.5"/>'
                f'<text x="76" y="534" font-family="{MONO}" font-size="14" font-weight="700" letter-spacing="4" fill="#b994a4">CONTRIBUTIONS · LAST 26 WEEKS</text>'
                f'<text x="1524" y="534" text-anchor="end" font-family="{MONO}" font-size="14" font-weight="700" letter-spacing="3" fill="#6ee7b7">{fmt(d["total"])} TOTAL</text></g>')
    weeks = d["weeks"]
    if weeks:
        mx = max(weeks) or 1
        bw = 1400 / len(weeks)
        for i, v in enumerate(weeks):
            h = max(4, 58 * v / mx)
            x = 76 + i * bw
            col = "#34d399" if v > 0.66 * mx else "#B48CFF" if v > 0.33 * mx else "#87536a"
            body.append(f'<rect x="{x:.1f}" y="{610-h:.1f}" width="{bw-6:.1f}" height="{h:.1f}" rx="3" fill="{col}" opacity=".9"><animate attributeName="opacity" values="0;0;.9" keyTimes="0;{0.2+i*0.025:.3f};1" dur="2s" fill="freeze"/><animate attributeName="height" values="{h:.1f};{h*0.92:.1f};{h:.1f}" dur="4s" begin="{i*0.15:.2f}s" repeatCount="indefinite"/></rect>')
    else:
        body.append(f'<text x="76" y="586" font-family="{SANS}" font-style="italic" font-size="20" fill="#cdb3bf">The contribution graph appears when the Action runs with a token.</text>')
    body.append(f'<text x="42" y="{H-18}" font-family="{MONO}" font-size="14" font-weight="700" letter-spacing="3" fill="#b994a4">@{esc(USER)} · UPDATED {NOW.strftime("%d %b %Y · %H:%M UTC").upper()}</text>')
    stamp = ""
    if d["longest"] is not None:
        stamp = f'LONGEST STREAK {d["longest"]} DAYS'
        body.append(f'<text x="{W-42}" y="{H-18}" text-anchor="end" font-family="{MONO}" font-size="14" font-weight="700" letter-spacing="3" fill="#b994a4">{stamp}</text>')
    return base(W, H, f"GitHub stats for {USER}", "Repositories, stars, followers, commits, pull requests, streak, top languages and a weekly contribution chart.",
                "GITHUB STATS", "Numbers that ship", "Generated automatically by a GitHub Action, so it never goes stale.", body, seed=31)


# ------------------------------------------------------------------ activity.svg
def ago(ts):
    t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    s = int((NOW - t).total_seconds())
    for n, unit in ((86400 * 30, "mo"), (86400, "d"), (3600, "h"), (60, "m")):
        if s >= n:
            return f"{s // n}{unit} ago"
    return "just now"


def describe(e):
    t, p, repo = e["type"], e.get("payload", {}), e["repo"]["name"]
    if t == "PushEvent":
        n = p.get("size") or len(p.get("commits", [])) or 1
        return ("Pushed {n} commit" + ("s" if n != 1 else "") + " to").format(n=n), "#34d399", repo, n
    if t == "CreateEvent":
        return f"Created a {p.get('ref_type', 'repository')} in", "#B48CFF", repo, 0
    if t == "PullRequestEvent":
        pr = p.get("pull_request", {})
        verb = "Merged" if pr.get("merged") else ("Opened" if p.get("action") == "opened" else "Closed")
        return f"{verb} a pull request in", "#60a5fa", repo, 0
    if t == "IssuesEvent":
        return f"{p.get('action', 'Updated').capitalize()} an issue in", "#f472b6", repo, 0
    if t == "WatchEvent":
        return "Starred", "#FFB84D", repo, 0
    if t == "ForkEvent":
        return "Forked", "#FFB84D", repo, 0
    if t == "ReleaseEvent":
        return "Published a release in", "#34d399", repo, 0
    if t in ("IssueCommentEvent", "PullRequestReviewEvent", "PullRequestReviewCommentEvent"):
        return "Commented in", "#a78bfa", repo, 0
    return None


def activity_svg():
    events = api(f"/users/{USER}/events/public?per_page=100") or []
    rows = []
    for e in events:
        r = describe(e)
        if not r:
            continue
        text, col, repo, n = r
        if rows and e["type"] == "PushEvent" and rows[-1]["type"] == "PushEvent" and rows[-1]["repo"] == repo:
            rows[-1]["n"] += n
            rows[-1]["text"] = f"Pushed {rows[-1]['n']} commits to"
            continue
        rows.append({"type": e["type"], "text": text, "col": col, "repo": repo, "n": n, "time": ago(e["created_at"])})
        if len(rows) == 6:
            break
    W = 1600
    RH = 78
    H = 200 + max(len(rows), 1) * RH + 70
    body = [f'<path id="tl" d="M92,200 V{H-70}" stroke="#87536a" stroke-opacity=".5" stroke-width="2" stroke-dasharray="3 8"><animate attributeName="stroke-dashoffset" values="0;22" dur="1.6s" repeatCount="indefinite"/></path>',
            f'<circle r="5" fill="#ecfeff" filter="url(#glow)"><animateMotion dur="6s" repeatCount="indefinite"><mpath xlink:href="#tl"/></animateMotion></circle>']
    if not rows:
        body.append(f'<text x="120" y="250" font-family="{SANS}" font-style="italic" font-size="26" fill="#cdb3bf">No public activity yet. Push something and check back tomorrow.</text>')
    for i, r in enumerate(rows):
        y = 190 + i * RH
        repo = r["repo"] if len(r["repo"]) <= 40 else r["repo"][:39] + "…"
        col = r["col"]
        body.append(f'''<g transform="translate(48,{y})"><g class="card" style="animation-delay:{0.3+i*0.12:.2f}s">
<rect width="1504" height="62" rx="20" fill="{col}" fill-opacity=".05" stroke="{col}" stroke-opacity=".35" stroke-width="1.4"><animate attributeName="stroke-opacity" values=".3;1;1;.3;.3" keyTimes="0;.04;.2;.24;1" dur="12s" begin="{i*2}s" repeatCount="indefinite"/></rect>
<rect x="1" y="1" width="4" height="60" rx="2" fill="{col}" fill-opacity=".85"/>
<circle cx="44" cy="31" r="10" fill="{col}" filter="url(#glow)"><animate attributeName="opacity" values="1;.5;1" dur="2.4s" begin="{i*0.3:.1f}s" repeatCount="indefinite"/></circle><circle cx="44" cy="31" r="10" fill="none" stroke="{col}" stroke-width="1.5"><animate attributeName="r" values="10;24" dur="2.8s" begin="{i*0.4:.1f}s" repeatCount="indefinite"/><animate attributeName="opacity" values=".6;0" dur="2.8s" begin="{i*0.4:.1f}s" repeatCount="indefinite"/></circle>
<text x="86" y="39" font-family="{SANS}" font-style="italic" font-size="24" fill="#e6d3dc">{esc(r["text"])} <tspan font-family="{MONO}" font-style="normal" font-weight="700" fill="{col}">{esc(repo)}</tspan></text>
<text x="1470" y="39" text-anchor="end" font-family="{MONO}" font-size="16" font-weight="700" letter-spacing="2" fill="#b994a4">{esc(r["time"]).upper()}</text></g></g>''')
    body.append(f'<text x="42" y="{H-18}" font-family="{MONO}" font-size="14" font-weight="700" letter-spacing="3" fill="#b994a4">@{esc(USER)} · PUBLIC ACTIVITY · UPDATED {NOW.strftime("%d %b %Y · %H:%M UTC").upper()}</text>')
    svg = base(W, H, f"Latest GitHub activity for {USER}", "The most recent public GitHub events, refreshed automatically.",
               "LATEST ACTIVITY", "What I'm shipping", "My most recent public GitHub events, refreshed automatically.", body, seed=32)
    return svg.replace('<svg xmlns="http://www.w3.org/2000/svg"', '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"', 1)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    data = collect()
    print("stats:", {k: v for k, v in data.items() if k != "weeks"})
    open(os.path.join(OUT, "stats.svg"), "w", encoding="utf-8").write(stats_svg(data))
    open(os.path.join(OUT, "activity.svg"), "w", encoding="utf-8").write(activity_svg())
    print("wrote", OUT)
