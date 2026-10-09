# Profile artwork

Run `python3 scripts/generate_profile.py` with Python 3.9+ and `GH_TOKEN`
(or `GITHUB_TOKEN`), or a locally authenticated GitHub CLI. No Python packages
are required. Never put a token in the repository.

The generator reads GitHub GraphQL contribution calendars and public, owned,
non-fork repositories (paginated), stars, and followers for `soufianziani`.
The checked-in JSON records the exact daily counts used to render the SVGs.
Contribution visibility follows GitHub's API and the account's settings;
repository names, private metadata, and credentials are never stored.

The heatmap and contribution total cover exactly 365 UTC dates, including today.
Both streak metrics are bounded by that window, not all-time. An empty current
UTC day preserves yesterday's streak until the day ends. The longest streak may
start before the window; only days within the window are counted.

## Refresh and validation

The workflow runs daily at 05:23 UTC, manually, and after generator changes on
main. Scheduled workflows start after merge into the default branch and may be
delayed by GitHub. GitHub may disable schedules in inactive public repositories;
re-enable the workflow in Actions if needed. It uses the built-in GitHub token
with write permission only for the refresh job. Branch rules must permit the
bot's generated-asset commits. Failures leave previously committed assets intact.
Pull requests only run offline validation with read permissions.

```
python3 -m unittest discover -s tests -v
python3 scripts/generate_profile.py --data assets/profile-data.json --output /tmp/profile-art
diff -r assets /tmp/profile-art
```

All four SVGs are self-contained: no scripts, remote fonts, or embedded HTML.
CSS animations reveal the cells, type the name, blink the cursor, and animate
statistics into view. Reduced-motion readers receive the complete static artwork.
If an image renderer disables CSS animation, final content remains visible.
README images scale to the container; the two 420px cards wrap on narrow screens
without a fixed-width HTML table. Plain text identity, skills, social links,
alt text, and original views/follower/star badges are retained.

Design inspiration: https://github.com/AVIVASHISHTA29 (terminal chrome,
contribution-first order, dark background, green accents). All SVGs and scripts
here are original, with Soufiane's information and live contribution data.
