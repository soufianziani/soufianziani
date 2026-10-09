#!/usr/bin/env python3
"""Generate self-contained profile SVGs from GitHub's API (Python stdlib only)."""
import argparse
from datetime import date, datetime, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOGIN = 'soufianziani'
COLORS = ['#161b22', '#0e4429', '#006d32', '#26a641', '#39d353']
LEVELS = ['NONE', 'FIRST_QUARTILE', 'SECOND_QUARTILE', 'THIRD_QUARTILE', 'FOURTH_QUARTILE']
QUERY = '''query($login:String!, $from:DateTime!, $to:DateTime!, $cursor:String) {
 user(login:$login) { login followers { totalCount }
 repositories(first:100, after:$cursor, privacy:PUBLIC, ownerAffiliations:OWNER) {
 totalCount nodes { stargazerCount } pageInfo { hasNextPage endCursor }
 }
 contributionsCollection(from:$from, to:$to) { contributionCalendar {
 totalContributions weeks { contributionDays { date contributionCount contributionLevel weekday } }
 } }
 }
}'''


def fetch(today):
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not token:
        token = subprocess.check_output(['gh', 'auth', 'token'], text=True).strip()
    start = today - timedelta(days=364)
    variables = dict(login=LOGIN, **{'from': f'{start}T00:00:00Z', 'to': f'{today}T23:59:59Z'}, cursor=None)
    stars = 0
    while True:
        request = urllib.request.Request('https://api.github.com/graphql',
            data=json.dumps(dict(query=QUERY, variables=variables)).encode(),
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', 'User-Agent': 'soufianziani-profile'})
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.load(response)
        if result.get('errors') or not result.get('data', {}).get('user'):
            raise ValueError('GitHub did not return a complete profile; existing assets were preserved')
        user = result['data']['user']
        repos = user['repositories']
        stars += sum(repo['stargazerCount'] for repo in repos['nodes'])
        if not repos['pageInfo']['hasNextPage']:
            break
        variables['cursor'] = repos['pageInfo']['endCursor']
    return dict(login=user['login'], as_of=str(today), stars=stars,
                followers=user['followers']['totalCount'], repositories=repos['totalCount'],
                calendar=user['contributionsCollection']['contributionCalendar'])


def days_of(data):
    days = [day for week in data['calendar']['weeks'] for day in week['contributionDays']]
    if not days or data['login'] != LOGIN:
        raise ValueError('Missing contribution days or incorrect GitHub account')
    dates = [date.fromisoformat(day['date']) for day in days]
    if any(b - a != timedelta(days=1) for a, b in zip(dates, dates[1:])):
        raise ValueError('Contribution calendar must contain consecutive days')
    if dates[-1] != date.fromisoformat(data['as_of']):
        raise ValueError('Calendar does not end on the snapshot date')
    for day in days:
        if day['contributionCount'] < 0 or day['contributionLevel'] not in LEVELS:
            raise ValueError('Invalid contribution data')
    if sum(day['contributionCount'] for day in days) != data['calendar']['totalContributions']:
        raise ValueError('Contribution total does not match the calendar')
    return days


def streaks(days, today):
    counts = {date.fromisoformat(d['date']): d['contributionCount'] for d in days}
    best = run = 0
    for day in days:
        run = run + 1 if day['contributionCount'] else 0
        best = max(best, run)
    cursor = today if counts.get(today, 0) else today - timedelta(days=1)
    current = 0
    while counts.get(cursor, 0):
        current += 1
        cursor -= timedelta(days=1)
    return current, best


def text(x, y, value, size=14, color='#c9d1d9', extra=''):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" {extra}>{escape(str(value))}</text>'


def svg(width, height, title, content):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title><desc id="desc">Soufiane Ziani's GitHub profile. Animations respect reduced motion; all information remains visible without animation.</desc>
<style>
text {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }}
.cell {{ animation: reveal 6s ease both infinite; animation-delay: var(--delay); }}
.metric {{ animation: reveal 1.2s ease both; }}
.type {{ animation: typing 7s steps(36, end) infinite; }}
.cursor {{ animation: blink 1s steps(2, start) infinite; }}
@keyframes reveal {{ 0% {{ opacity: .2; }} 20%,100% {{ opacity: 1; }} }}
@keyframes typing {{ 0%,8% {{ clip-path: inset(0 100% 0 0); }} 45%,95% {{ clip-path: inset(0 0 0 0); }} 100% {{ clip-path: inset(0 100% 0 0); }} }}
@keyframes blink {{ to {{ opacity: 0; }} }}
@media (prefers-reduced-motion: reduce) {{ .cell,.metric,.type,.cursor {{ animation: none !important; }} }}
</style>
<rect x=".5" y=".5" width="{width-1}" height="{height-1}" rx="10" fill="#0d1117" stroke="#30363d"/>
<path d="M1 34H{width-1}" stroke="#30363d"/>
<circle cx="18" cy="18" r="4" fill="#ff5f57"/><circle cx="32" cy="18" r="4" fill="#febc2e"/><circle cx="46" cy="18" r="4" fill="#28c840"/>
{text(64,22,title,10,'#8b949e')}
{content}
</svg>\n'''


def heatmap(data, days):
    parts = []
    weeks = data['calendar']['weeks']
    step = min(14, 752 / len(weeks))
    previous = None
    for wi, week in enumerate(weeks):
        for day in week['contributionDays']:
            dt = date.fromisoformat(day['date'])
            if dt.month != previous:
                # Keep the last, partial month label within the viewBox.
                if wi < len(weeks) - 2:
                    parts.append(text(56 + wi * step, 61, dt.strftime('%b'), 10, '#8b949e'))
                previous = dt.month
            x, y = 56 + wi * step, 76 + day['weekday'] * 16
            level = LEVELS.index(day['contributionLevel'])
            parts.append(f'<rect class="cell" style="--delay:{wi*.035:.3f}s" x="{x:.2f}" y="{y}" width="{step-3:.2f}" height="12" rx="2" fill="{COLORS[level]}"><title>{day["date"]}: {day["contributionCount"]} contributions</title></rect>')
    for label, row in [('Mon',1),('Wed',3),('Fri',5)]:
        parts.append(text(20,86+row*16,label,10,'#8b949e'))
    parts += [text(22,211,f'{data["calendar"]["totalContributions"]:,} contributions',16,'#39d353'),
              text(22,234,f'{days[0]["date"]} to {days[-1]["date"]} · refreshed daily (UTC)',11,'#8b949e'), text(654,211,'Less',10,'#8b949e')]
    for i, color in enumerate(COLORS):
        parts.append(f'<rect x="{686+i*16}" y="201" width="12" height="12" rx="2" fill="{color}"/>')
    parts.append(text(771,211,'More',10,'#8b949e'))
    return svg(840,254,'soufiane@github:~ $ ./contributions.sh','\n'.join(parts))


def terminal():
    parts = [text(22,71,'$ whoami',15,'#39d353'), text(22,110,'SOUFIANE ZIANI',28,'#f0f6fc'),
             text(22,143,'Software Developer',16,'#39d353', 'class="type"'),
             text(22,187,'$ cat skills.txt',14,'#39d353')]
    for i, skill in enumerate(['Flutter Developer', 'Backend Systems', 'APIs', 'Automation']):
        parts.append(text(22,218+i*28,f'> {skill}',16))
    parts += [text(22,363,'soufianziani / README.md',11,'#8b949e'),text(22,401,'$ ',16,'#39d353'),
              '<rect class="cursor" x="42" y="387" width="9" height="17" fill="#39d353"/>']
    return svg(410,426,'~/profile / whoami','\n'.join(parts))


def stats(data, days):
    current, best = streaks(days,date.fromisoformat(data['as_of']))
    metrics = [('current streak',f'{current} day' + ('s' if current != 1 else '')),('longest in window',f'{best} day' + ('s' if best != 1 else '')),
               ('contributions',f'{data["calendar"]["totalContributions"]:,}'),('active days',str(sum(d['contributionCount']>0 for d in days))),
               ('public repositories',str(data['repositories'])),('public repo stars',str(data['stars']))]
    parts = []
    for i, (label,value) in enumerate(metrics):
        x, y = 16+(i%2)*194, 52+(i//2)*100
        parts.append(f'<g class="metric" style="animation-delay:{i*.12}s"><rect x="{x}" y="{y}" width="184" height="88" rx="6" fill="#161b22" stroke="#21262d"/>{text(x+12,y+23,label,11,"#8b949e")}{text(x+12,y+61,value,27,"#39d353" if i<2 else "#f0f6fc")}</g>')
    parts += [text(20,373,f'{data["followers"]} followers · refreshed {data["as_of"]}',11,'#8b949e'),
              text(20,397,'Streaks / activity: displayed year · UTC',10,'#8b949e')]
    return svg(410,426,'~/profile / stats.sh','\n'.join(parts))


def render(data, output):
    days = days_of(data)
    assets = {'contributions.svg': heatmap(data,days), 'terminal.svg': terminal(), 'stats.svg': stats(data,days)}
    output.mkdir(parents=True, exist_ok=True)
    for name, content in assets.items():
        target = output / name
        temporary = target.with_suffix('.tmp')
        temporary.write_text(content, encoding='utf-8')
        temporary.replace(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, help='Render an offline JSON snapshot instead of calling GitHub')
    parser.add_argument('--output', type=Path, default=ROOT/'assets')
    args = parser.parse_args()
    today = datetime.now(timezone.utc).date()
    data = json.loads(args.fixture.read_text()) if args.fixture else fetch(today)
    render(data,args.output)
    print(f'Generated 3 SVGs for {LOGIN}; data through {data["as_of"]}')

if __name__ == '__main__':
    main()
