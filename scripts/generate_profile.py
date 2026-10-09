#!/usr/bin/env python3
"""Generate self-contained, GitHub-compatible SVGs using GitHub's GraphQL API."""
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
GREEN = '#39d353'
QUERY = '''query($login:String!, $from:DateTime!, $to:DateTime!, $cursor:String) {
 user(login:$login) {
  followers { totalCount }
  repositories(first:100, after:$cursor, ownerAffiliations:OWNER, privacy:PUBLIC, isFork:false) {
   totalCount nodes { stargazerCount } pageInfo { hasNextPage endCursor }
  }
  contributionsCollection(from:$from, to:$to) {
   contributionCalendar { totalContributions weeks { contributionDays { date contributionCount contributionLevel } } }
  }
 }
}'''


def graphql(variables):
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    payload = json.dumps({'query': QUERY, 'variables': variables})
    if token:
        request = urllib.request.Request('https://api.github.com/graphql', data=payload.encode(),
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', 'User-Agent': 'profile-art'})
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.load(response)
    else:
        result = json.loads(subprocess.check_output(['gh', 'api', 'graphql', '--input', '-'], input=payload, text=True))
    if result.get('errors') or not result.get('data', {}).get('user'):
        raise RuntimeError('GitHub query failed; existing assets were not replaced')
    return result['data']['user']


def fetch(today):
    start = today - timedelta(days=364)
    variables = {'login': LOGIN, 'from': f'{start}T00:00:00Z', 'to': f'{today}T23:59:59Z', 'cursor': None}
    user = graphql(variables)
    calendar = user['contributionsCollection']['contributionCalendar']
    repos = user['repositories']
    stars = sum(r['stargazerCount'] for r in repos['nodes'])
    while repos['pageInfo']['hasNextPage']:
        variables['cursor'] = repos['pageInfo']['endCursor']
        repos = graphql(variables)['repositories']
        stars += sum(r['stargazerCount'] for r in repos['nodes'])
    days = [d for w in calendar['weeks'] for d in w['contributionDays'] if start.isoformat() <= d['date'] <= today.isoformat()]
    return {'login': LOGIN, 'as_of': str(today), 'days': days,
            'followers': user['followers']['totalCount'], 'repositories': user['repositories']['totalCount'], 'stars': stars}


def validate(data):
    if data['login'] != LOGIN:
        raise ValueError('Unexpected profile identity')
    today = date.fromisoformat(data['as_of'])
    expected = [str(today - timedelta(days=i)) for i in range(364, -1, -1)]
    if [d['date'] for d in data['days']] != expected:
        raise ValueError('Expected 365 complete, ordered UTC dates')
    for day in data['days']:
        if not isinstance(day['contributionCount'], int) or day['contributionCount'] < 0:
            raise ValueError('Invalid contribution count')
        if day['contributionLevel'] not in LEVELS:
            raise ValueError('Invalid contribution level')


def streaks(days):
    longest = run = 0
    for day in days:
        run = run + 1 if day['contributionCount'] else 0
        longest = max(longest, run)
    # An unfinished UTC day does not break yesterday's current streak.
    tail = days if days[-1]['contributionCount'] else days[:-1]
    current = 0
    for day in reversed(tail):
        if not day['contributionCount']:
            break
        current += 1
    return current, longest


LEVELS = {'NONE': '#161b22', 'FIRST_QUARTILE': '#0e4429', 'SECOND_QUARTILE': '#006d32', 'THIRD_QUARTILE': '#26a641', 'FOURTH_QUARTILE': GREEN}
STYLE = '''text{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;fill:#c9d1d9}
.reveal{animation:reveal .6s ease both}@keyframes reveal{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:translateY(0)}}
.cell{animation:cell .5s ease both}@keyframes cell{from{opacity:.15}to{opacity:1}}
.typing{animation:type 2.5s steps(28,end) both}@keyframes type{from{clip-path:inset(0 100% 0 0)}to{clip-path:inset(0 0 0 0)}}
.cursor{animation:blink 1s steps(2,start) infinite}@keyframes blink{50%{opacity:0}}
@media(prefers-reduced-motion:reduce){.reveal,.cell,.typing,.cursor{animation:none!important;opacity:1!important;transform:none!important;clip-path:none!important}}'''


def text(x, y, value, size=14, color=None, extra=''):
    fill = f' style="fill:{color}"' if color else ''
    return f'<text x="{x}" y="{y}" font-size="{size}"{fill} {extra}>{escape(str(value))}</text>'



def svg(width, height, title, body, description):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc><style>{STYLE}</style>
<rect x=".5" y=".5" width="{width-1}" height="{height-1}" rx="12" fill="#0d1117" stroke="#30363d"/>
<path d="M1 38H{width-1}" stroke="#30363d"/>
<circle cx="20" cy="19" r="4" fill="#ff5f56"/><circle cx="35" cy="19" r="4" fill="#ffbd2e"/><circle cx="50" cy="19" r="4" fill="#27c93f"/>
{text(70,23,title,11,'#8b949e')}{body}</svg>\n'''


def heatmap(data):
    days = data['days']
    first = date.fromisoformat(days[0]['date'])
    origin = first - timedelta(days=(first.weekday()+1) % 7)
    body = text(24, 72, 'CONTRIBUTION HISTORY', 13, GREEN)
    body += text(24, 100, f"{sum(d['contributionCount'] for d in days):,} contributions / last 365 days", 19)
    month = None
    for i, day in enumerate(days):
        current = date.fromisoformat(day['date'])
        offset = (current-origin).days
        x, y = 45 + (offset//7)*14.6, 140 + (offset%7)*17
        if current.month != month:
            if i == 0 or current.day == 1 and (current-first).days > 15:
                body += text(x, 128, current.strftime('%b'), 10, '#8b949e')
            month = current.month
        body += f'<rect class="cell" x="{x:.1f}" y="{y}" width="11" height="13" rx="2" fill="{LEVELS[day["contributionLevel"]]}" style="animation-delay:{i*.004:.3f}s"><title>{day["date"]}: {day["contributionCount"]} contributions</title></rect>'
    for row, label in [(1,'M'),(3,'W'),(5,'F')]:
        body += text(24,151+row*17,label,10,'#8b949e')
    body += text(24, 283, f"updated {data['as_of']} UTC", 11, '#8b949e')
    body += text(670,283,'less',10,'#8b949e')
    for i, color in enumerate(LEVELS.values()):
        body += f'<rect x="{702+i*16}" y="273" width="12" height="12" rx="2" fill="{color}"/>'
    body += text(787,283,'more',10,'#8b949e')
    return svg(860,306,'soufiane@github: ~/contributions',body,'Real GitHub contribution counts for the last 365 UTC dates. Cells reveal chronologically.')


def terminal():
    body = text(24,76,'$ whoami',15,GREEN)
    body += text(24,116,'SOUFIANE ZIANI',27,extra='class="typing"')
    lines = [('Software Developer', '#c9d1d9'), ('Flutter Developer', '#c9d1d9'), ('$ cat skills.txt', GREEN), ('Backend Systems', '#c9d1d9'), ('APIs / Automation', '#c9d1d9')]
    for i,(line,color) in enumerate(lines):
        body += f'<g class="reveal" style="animation-delay:{.3+i*.16}s">{text(24,155+i*30,line,16,color)}</g>'
    body += text(24,328,'soufiane@github ~ $',14,GREEN)
    body += '<rect class="cursor" x="192" y="315" width="9" height="16" fill="#39d353"/>'
    return svg(420,356,'soufiane@github: ~',body,'Soufiane Ziani. Software Developer, Flutter Developer, Backend Systems, APIs, Automation.')


def cards(data):
    current,longest = streaks(data['days'])
    values = [(data['repositories'],'public repos'),(data['stars'],'stars earned'),(data['followers'],'followers'),(sum(d['contributionCount'] for d in data['days']),'contributions')]
    body = text(24,73,'$ ./stats.sh',15,GREEN)
    for i,(value,label) in enumerate(values):
        x,y = 24+(i%2)*194, 98+(i//2)*104
        body += f'<g class="reveal" style="animation-delay:{i*.15}s"><rect x="{x}" y="{y}" width="178" height="90" rx="8" fill="#161b22"/>{text(x+14,y+39,f"{value:,}",29,GREEN)}{text(x+14,y+65,label,12,"#8b949e")}</g>'
    body += text(24,329,'repos / stars: public, non-fork',11,'#8b949e')
    stats = svg(420,356,'soufiane@github: ~/stats',body,f"{values}. Contributions cover the last 365 days. Updated {data['as_of']} UTC.")
    body = text(24,74,'$ ./streak.sh --window 365d',15,GREEN)
    for i,(value,label) in enumerate([(current,'CURRENT STREAK'),(longest,'LONGEST IN WINDOW')]):
        x = 24+i*418
        body += f'<g class="reveal" style="animation-delay:{i*.25}s">{text(x,127,str(value),40,GREEN)}{text(x+90,125,"days",15,"#8b949e")}{text(x,157,label,12)}</g>'
    body += text(24,195,f"UTC calendar / through {data['as_of']} / today may still be in progress",11,'#8b949e')
    streak = svg(860,218,'soufiane@github: ~/streak',body,f'Current streak {current} days; longest within the last 365 days {longest} days. Not an all-time streak.')
    return stats,streak


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, help='Render an existing snapshot without API access')
    parser.add_argument('--output', type=Path, default=ROOT/'assets')
    args = parser.parse_args()
    data = json.loads(args.data.read_text()) if args.data else fetch(datetime.now(timezone.utc).date())
    validate(data)
    stats,streak = cards(data)
    artifacts = {'contributions.svg':heatmap(data), 'terminal.svg':terminal(), 'stats.svg':stats, 'streak.svg':streak,
                 'profile-data.json':json.dumps(data,indent=2)+'\n'}
    args.output.mkdir(parents=True,exist_ok=True)
    for name, content in artifacts.items():
        (args.output/name).write_text(content)
    print(f"Generated {len(artifacts)} assets for {LOGIN} as of {data['as_of']}")


if __name__ == '__main__':
    main()
