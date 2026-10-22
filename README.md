# The TechnoScribe — Lead Radar

Local-first lead discovery for fractional PMM, technical content, and developer marketing opportunities.

## Mac installation (one-time)

Open Terminal and run:

```bash
git clone https://github.com/gedalyahreback/leadradar.git
cd leadradar
python3 server.py
```

Open http://127.0.0.1:8765

Requires Python 3.9+. No pip or npm dependencies.

## Updates

Stop the server with Ctrl+C, then from the **leadradar** folder:

```bash
git pull
python3 server.py
```

Your data stays in the local file `lead_radar.sqlite3`. **Never commit that database to GitHub** (the .gitignore excludes it). When migrating from a ZIP installation, copy its `lead_radar.sqlite3` into the cloned repository folder once, while the server is stopped.

## Connections.csv upload

LinkedIn's data archive often puts explanatory lines above the real header. The importer scans for the `First Name,Last Name` header, supports UTF-8 BOM and alternative case/spaces, and reports imported, skipped and matched totals. A CSV of connections is required, not the ZIP archive or the invitations export. The upload limit is 15MB. Connections are stored locally only; name-based matches still need human verification.

## Search

Google, Bing, and Brave links open browser search results for publicly indexed LinkedIn posts. Optional live Bing RSS is experimental. Live Brave API requires `BRAVE_API_KEY` as an environment variable. Neither reads private LinkedIn data. Search-location hints are not verified poster locations. India-based posters are excluded from saved prospects. The tool does not automatically contact anyone.
