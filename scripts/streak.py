"""Render assets/streak.svg: contribution streaks plus profile numbers.

Usage: python scripts/streak.py <github-user> <output.svg>
No token needed: it reads https://github.com/users/<user>/contributions year by year,
the public REST API for repos/stars, and the komarev badge for profile views.
"""
import json
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
UA = {"User-Agent": "profile-streak-card"}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def profile(user, today):
    info = json.loads(fetch(f"https://api.github.com/users/{user}"))
    repos = json.loads(fetch(f"https://api.github.com/users/{user}/repos?per_page=100&type=owner"))
    badge = fetch(f"https://komarev.com/ghpvc/?username={user}&style=flat-square")
    views = re.findall(r"<text[^>]*>([\d,]+)</text>", badge)
    return {
        "created": info["created_at"],
        "repos": info["public_repos"],
        "stars": sum(r["stargazers_count"] for r in repos if not r["fork"]),
        "days": (today - date.fromisoformat(info["created_at"][:10])).days,
        "views": int(views[-1].replace(",", "")) if views else 0,
    }


def contributions(user, created, today):
    days = {}
    for year in range(int(created[:4]), today.year + 1):
        html = fetch(f"https://github.com/users/{user}/contributions?from={year}-01-01&to={year}-12-31")
        dates = dict(re.findall(r'data-date="(\d{4}-\d{2}-\d{2})" id="([^"]+)"', html))
        id_to_date = {v: k for k, v in dates.items()}
        for cell_id, label in re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)', html):
            d = id_to_date.get(cell_id)
            if not d:
                continue
            m = re.match(r"(\d+) contribution", label.replace(",", ""))
            days[date.fromisoformat(d)] = int(m.group(1)) if m else 0
    return {d: c for d, c in days.items() if d <= today}


def stats(days, today):
    total = sum(days.values())
    first = min((d for d, c in days.items() if c), default=today)

    # A streak stays alive if today has no contributions yet.
    cur_end = today if days.get(today) else today - timedelta(days=1)
    cur_start, d = None, cur_end
    while days.get(d):
        cur_start, d = d, d - timedelta(days=1)
    current = (cur_end - cur_start).days + 1 if cur_start else 0

    longest, best, run_start = 0, (None, None), None
    for d in sorted(days):
        if days[d]:
            run_start = run_start or d
            length = (d - run_start).days + 1
            if length > longest:
                longest, best = length, (run_start, d)
        else:
            run_start = None

    last30 = [days.get(today - timedelta(days=i), 0) for i in range(29, -1, -1)]
    return {
        "total": total, "first": first,
        "current": current, "cur_range": (cur_start, cur_end) if current else (None, None),
        "longest": longest, "best_range": best,
        "last30": last30,
    }


def fmt(d):
    return d.strftime("%b %-d, %Y") if d else ""


def fmt_range(r):
    a, b = r
    if not a:
        return "Start a new streak today"
    return fmt(a) if a == b else f"{fmt(a)} – {fmt(b)}"


def render(user, s, p, now):
    peak = max(s["last30"]) or 1
    bars = []
    for i, c in enumerate(s["last30"]):
        h = 4 + 36 * c / peak
        if c:
            # staggered delay makes the bars pulse as a wave from left to right
            bars.append(f'<rect class="bar-on" fill="url(#bar-grad)" style="animation-delay:{i * 0.08:.2f}s" '
                        f'x="{60 + i * 30}" y="{286 - h:.1f}" width="20" height="{h:.1f}"/>')
        else:
            bars.append(f'<rect class="bar" x="{60 + i * 30}" y="{286 - h:.1f}" width="20" height="{h:.1f}"/>')

    tiles = [("Profile Views", p["views"]), ("Public Repos", p["repos"]), ("Stars", p["stars"]), ("Days on GitHub", p["days"])]
    tile_svg = "".join(
        f'<text class="tile-{i + 1}" x="{125 + i * 250}" y="190" font-size="22" font-weight="700" text-anchor="middle">{v:,}</text>'
        f'<text class="t-muted" x="{125 + i * 250}" y="210" font-size="13" text-anchor="middle">{k}</text>'
        for i, (k, v) in enumerate(tiles)
    )

    return f'''<svg width="1000" height="330" viewBox="0 0 1000 330" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="GitHub streak for {user}">
  <style>
    text {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; }}
    .mono {{ font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; }}

    .card-bg  {{ fill: #f6f8fa; }}
    .card-bd  {{ fill: none; stroke: #d0d7de; stroke-width: 1; }}
    .divider  {{ stroke: #d0d7de; stroke-width: 1; }}
    .t-title  {{ fill: #1f2328; }}
    .t-muted  {{ fill: #636c76; }}
    .t-subtle {{ fill: #6e7781; }}
    .accent   {{ fill: #0969da; }}
    .ring     {{ fill: none; stroke-width: 5; }}
    .bar      {{ fill: #d0d7de; }}
    .tile-1   {{ fill: #0969da; }}
    .tile-2   {{ fill: #bf3989; }}
    .tile-3   {{ fill: #8250df; }}
    .tile-4   {{ fill: #1a7f37; }}
    .cy-base  {{ stop-color: #0e7490; }}
    .cy-glow  {{ stop-color: #22d3ee; }}
    .bar-top  {{ stop-color: #22d3ee; }}
    .bar-mid  {{ stop-color: #0969da; }}
    .bar-low  {{ stop-color: #8250df; }}
    .glow     {{ fill: none; stroke: #22d3ee; stroke-width: 10; opacity: .15; }}

    @keyframes wave  {{ 0%, 100% {{ opacity: .55; }} 50% {{ opacity: 1; }} }}
    @keyframes pulse {{ 0%, 100% {{ opacity: .05; }} 50% {{ opacity: .35; }} }}
    .bar-on   {{ animation: wave 2.4s ease-in-out infinite; }}
    .glow     {{ animation: pulse 2.4s ease-in-out infinite; }}

    @media (prefers-color-scheme: dark) {{
      .card-bg  {{ fill: #161b22; }}
      .card-bd  {{ stroke: #30363d; }}
      .divider  {{ stroke: #30363d; }}
      .t-title  {{ fill: #e6edf3; }}
      .t-muted  {{ fill: #9198a1; }}
      .t-subtle {{ fill: #848d97; }}
      .accent   {{ fill: #58a6ff; }}
      .bar      {{ fill: #21262d; }}
      .tile-1   {{ fill: #58a6ff; }}
      .tile-2   {{ fill: #f778ba; }}
      .tile-3   {{ fill: #a371f7; }}
      .tile-4   {{ fill: #3fb950; }}
      .cy-base  {{ stop-color: #0891b2; }}
      .cy-glow  {{ stop-color: #a5f3fc; }}
      .bar-mid  {{ stop-color: #58a6ff; }}
      .bar-low  {{ stop-color: #a371f7; }}
    }}
  </style>

  <defs>
    <!-- rainbow for the top strip and the streak ring -->
    <linearGradient id="rainbow-strip" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="500" y2="0" spreadMethod="repeat">
      <stop offset="0" stop-color="#ff3b30"/><stop offset=".17" stop-color="#ff9500"/>
      <stop offset=".33" stop-color="#ffcc00"/><stop offset=".5" stop-color="#34c759"/>
      <stop offset=".67" stop-color="#00c7be"/><stop offset=".83" stop-color="#af52de"/>
      <stop offset="1" stop-color="#ff3b30"/>
      <animateTransform attributeName="gradientTransform" type="translate" from="0 0" to="500 0" dur="4s" repeatCount="indefinite"/>
    </linearGradient>
    <linearGradient id="rainbow-ring" gradientUnits="userSpaceOnUse" x1="464" y1="0" x2="536" y2="0">
      <stop offset="0" stop-color="#ff3b30"/><stop offset=".2" stop-color="#ffcc00"/>
      <stop offset=".4" stop-color="#34c759"/><stop offset=".6" stop-color="#00c7be"/>
      <stop offset=".8" stop-color="#5856d6"/><stop offset="1" stop-color="#af52de"/>
      <animateTransform attributeName="gradientTransform" type="rotate" from="0 500 58" to="360 500 58" dur="3s" repeatCount="indefinite"/>
    </linearGradient>
    <!-- cyan highlight sliding across the big numbers, same as the header slogan -->
    <linearGradient id="cyan-slide" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="1000" y2="0">
      <stop offset="0" class="cy-base"/><stop offset=".44" class="cy-base"/>
      <stop offset=".5" class="cy-glow"/><stop offset=".56" class="cy-base"/>
      <stop offset="1" class="cy-base"/>
      <animateTransform attributeName="gradientTransform" type="translate" from="-600 0" to="600 0" dur="3.2s" repeatCount="indefinite"/>
    </linearGradient>
    <linearGradient id="bar-grad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" class="bar-top"/><stop offset=".5" class="bar-mid"/><stop offset="1" class="bar-low"/>
    </linearGradient>
  </defs>

  <rect class="card-bg" x="0.5" y="0.5" width="999" height="329"/>
  <rect class="card-bd" x="0.5" y="0.5" width="999" height="329"/>
  <rect x="0.5" y="0.5" width="999" height="4" fill="url(#rainbow-strip)"/>

  <line class="divider" x1="333" y1="24" x2="333" y2="128"/>
  <line class="divider" x1="666" y1="24" x2="666" y2="128"/>

  <text fill="url(#cyan-slide)" x="166" y="72" font-size="34" font-weight="700" text-anchor="middle">{s["total"]:,}</text>
  <text class="t-muted" x="166" y="100" font-size="15" text-anchor="middle">Total Contributions</text>
  <text class="t-subtle" x="166" y="120" font-size="12" text-anchor="middle">{fmt(s["first"])} – Present</text>

  <circle class="glow" cx="500" cy="58" r="36"/>
  <circle class="ring" cx="500" cy="58" r="36" stroke="url(#rainbow-ring)"/>
  <text fill="url(#cyan-slide)" x="500" y="70" font-size="32" font-weight="700" text-anchor="middle">{s["current"]}</text>
  <text class="accent" x="500" y="114" font-size="15" font-weight="600" text-anchor="middle">Current Streak</text>
  <text class="t-subtle" x="500" y="132" font-size="12" text-anchor="middle">{fmt_range(s["cur_range"])}</text>

  <text fill="url(#cyan-slide)" x="833" y="72" font-size="34" font-weight="700" text-anchor="middle">{s["longest"]}</text>
  <text class="t-muted" x="833" y="100" font-size="15" text-anchor="middle">Longest Streak</text>
  <text class="t-subtle" x="833" y="120" font-size="12" text-anchor="middle">{fmt_range(s["best_range"])}</text>

  <line class="divider" x1="60" y1="156" x2="940" y2="156"/>
  <line class="divider" x1="250" y1="172" x2="250" y2="214"/>
  <line class="divider" x1="500" y1="172" x2="500" y2="214"/>
  <line class="divider" x1="750" y1="172" x2="750" y2="214"/>
  {tile_svg}

  <text class="mono t-subtle" x="60" y="240" font-size="12">// last 30 days</text>
  <text class="mono t-subtle" x="940" y="240" font-size="12" text-anchor="end">updated {now:%Y-%m-%d %H:%M} ICT</text>
  {"".join(bars)}
</svg>
'''


def main():
    user, out = sys.argv[1], sys.argv[2]
    now = datetime.now(TZ)
    p = profile(user, now.date())
    s = stats(contributions(user, p["created"], now.date()), now.date())
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(user, s, p, now))
    print(f"total={s['total']} current={s['current']} longest={s['longest']} "
          f"views={p['views']} repos={p['repos']} stars={p['stars']} days={p['days']}")


if __name__ == "__main__":
    main()
