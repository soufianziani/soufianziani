# Terminal profile artwork

Run `python3 -m unittest discover -s tests -v`, then `python3 scripts/generate_profile.py` with Python 3.9+ and either `GH_TOKEN` / `GITHUB_TOKEN` or an authenticated GitHub CLI. The generator uses only the Python standard library and GitHub GraphQL API. Tokens never appear in generated output. No additional secret or external statistics service is required in Actions.

For an offline preview, run `python3 scripts/generate_profile.py --fixture tests/fixtures/profile.json --output /tmp/profile-art`. The fixture is synthetic test data; published assets are generated from the live account.

The workflow tests pull requests without write permissions. On main it refreshes daily at 05:23 UTC, after generator changes, or via **Actions → Refresh terminal profile → Run workflow**. Schedules become active after merge into the default branch and may be delayed by GitHub. Repository rules must permit the Actions bot to commit generated assets; a rejected push fails visibly without force-pushing. In inactive public repositories GitHub may disable schedules after 60 days; re-enable in Actions if necessary.

API failures or invalid calendars fail before replacing artwork. Last good SVGs stay available. Public repository/star totals are paginated. Contribution totals and streaks cover the displayed 365-day window; current streak tolerates an unfinished UTC day. They do not claim an all-time record. GitHub's visibility rules can cause counts to differ from an authenticated private profile view.

All SVGs have a viewBox, dark GitHub colors, accessible titles, readable static states, and reduced-motion CSS. The README uses wrapping images instead of a fixed table. Update `terminal()` and the README together when changing skills. Social destinations are preserved from the previous README.

Visual inspiration: [AVIVASHISHTA29's terminal profile](https://github.com/AVIVASHISHTA29). Artwork and generator code here were written for Soufiane Ziani; no portrait, personal text, or statistics were copied.
