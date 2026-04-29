# TSA Tracker (tsatracker.com)

Real-time TSA security checkpoint wait times for major US airports. This platform pulls data directly from official airport systems every 2 minutes, provides historical trend analysis, and is optimized for both speed and search engines.

---

## 🚀 Live Airports
The following airports have verified, official data feeds currently integrated:

| Code | Airport Name | Data Source |
| :--- | :--- | :--- |
| **PHL** | Philadelphia International | Official Metrics API |
| **MIA** | Miami International | Rotating API Key (Auto-refreshing) |
| **ORD** | Chicago O'Hare | Official Wait Times API |
| **CLT** | Charlotte Douglas | `api.cltairport.mobi` Integration |
| **MCO** | Orlando International | `api.goaa.aero` Integration |
| **JAX** | Jacksonville International | HTML Table Scrape |
| **DFW** | Dallas/Fort Worth | `api.dfwairport.mobi` Integration |
| **LAX** | Los Angeles International | HTML Table Scrape |
| **JFK** | John F. Kennedy International | PANYNJ GraphQL API |
| **EWR** | Newark Liberty International | PANYNJ GraphQL API |
| **LGA** | LaGuardia Airport | PANYNJ GraphQL API |
| **SEA** | Seattle-Tacoma International | Drupal JSON API |

---

## 🛠 Features
- **Real-time Polling**: Background poller refreshes data every 120 seconds.
- **Historical Trends**: Stores samples in SQLite to generate 12-hour wait history charts.
- **X/Twitter Alerts**: Optional abnormal-wait posting built into the poller with cooldown-based dedupe.
- **Smart SEO**: Automatic landing pages for every airport (`/airports/phl-tsa-wait-times`) with structured JSON-LD data for search engines.
- **Monetization Ready**: Integrated slots for Google AdSense and affiliate CTAs (Uber, Lyft, Parking, Klook).
- **Lightweight UI**: Built with pure CSS and Vanilla JS for sub-second page loads.
- **Self-Healing**: Collectors for airports like MIA and CLT automatically re-scrape official site bundles if API keys expire.

---

## 📂 Project Structure
- `app.py`: Main Flask application, background poller, and data collectors.
- `airport_research/`: Detailed investigation logs for endpoint discovery and reverse engineering.
- `static/`: Frontend assets (styles, charts, search logic).
- `templates/`: Semantic HTML5 templates with Jinja2.
- `data.db`: SQLite database for wait-time samples.

---

## 💻 Getting Started

### Local Development
1. Clone the repository.
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the application:
   ```bash
   python app.py
   ```
5. Open `http://localhost:8080`.

---

## 🚢 Deployment
TSA Tracker is built for production readiness on **Render**, **Heroku**, or **Docker**.

### Render (Recommended)
This repository includes a `render.yaml` Blueprint.
1. Connect this repo to Render.
2. Confirm environment variables (refer to `.env.example`).
3. Deploy the `web` service for Flask and the `collector` worker for polling.

### Processes
- Web: `gunicorn --workers 1 --threads 4 --bind 0.0.0.0:$PORT wsgi:app`
- Collector once: `python collector.py --once`
- Collector loop: `python collector.py --loop`

### Environment Variables
| Variable | Description | Default |
| :--- | :--- | :--- |
| `ENABLE_POLLER` | Legacy toggle for choosing collector mode outside the web process | `true` |
| `POLL_SECONDS` | Interval between data refreshes | `120` |
| `DB_PATH` | Path to SQLite database | `data.db` |
| `COLLECT_NOW_TOKEN` | Secret token to trigger manual fetch via API | Required |
| `SITE_URL` | Used for Canonical URLs/SEO | `https://tsatracker.com` |
| `ENABLE_X_ALERTS` | Enable abnormal wait posting to X | `false` |
| `X_API_KEY` | X app API key | Required for X alerts |
| `X_API_SECRET` | X app API secret | Required for X alerts |
| `X_ACCESS_TOKEN` | X user access token | Required for X alerts |
| `X_ACCESS_TOKEN_SECRET` | X user access token secret | Required for X alerts |
| `X_ACCOUNT_HANDLE` | Account handle used for ops/docs | `TsaTracker` |
| `X_ALERT_MIN_WAIT` | Minimum average live wait before alert consideration | `35` |
| `X_ALERT_EXTREME_WAIT` | Alert even without baseline if current wait exceeds this | `50` |
| `X_ALERT_MIN_DELTA` | Minimum delta above historical baseline | `15` |
| `X_ALERT_COOLDOWN_MINUTES` | Minimum minutes between same-airport alerts | `90` |
| `X_ALERT_BASELINE_HOURS` | History window for baseline calculation | `6` |
| `X_ALERT_MIN_BASELINE_SAMPLES` | Minimum sample count before using a baseline | `12` |

### X/Twitter Alerts
This repo can automatically post abnormal TSA wait spikes to an X account from the existing poller loop.

Setup:
1. Create an X developer app and generate `API key`, `API secret`, `Access token`, and `Access token secret` for the posting account.
2. Add the env vars above in Render.
3. Set `ENABLE_X_ALERTS=true`.

Behavior:
- Evaluates each fresh collector cycle.
- Posts only when an airport's current average wait is materially high.
- Uses a rolling historical baseline plus a cooldown to reduce spam.
- Logs posted and failed attempts in the `social_posts` SQLite table.

---

## 🔎 Google Search Console Automation

This repo includes a minimal CLI for two repetitive Search Console tasks:
- submit `sitemap.xml`
- inspect index status for a shortlist of URLs

Script:
- `scripts/gsc_automation.py`

### Requirements
1. Enable the `Search Console API` in a Google Cloud project.
2. Create a Google `service account` and download its JSON key.
3. Add that service account email as a user or owner on your Search Console property.

### Env Vars
| Variable | Description |
| :--- | :--- |
| `GSC_PROPERTY` | Search Console property, e.g. `https://tsatracker.com/` or `sc-domain:tsatracker.com` |
| `GSC_SERVICE_ACCOUNT_FILE` | Path to the service account JSON file |
| `GSC_SITEMAP_URL` | Absolute sitemap URL, e.g. `https://tsatracker.com/sitemap.xml` |
| `GSC_LANGUAGE_CODE` | Optional inspection language code, e.g. `en-US` |

### Usage
Submit the sitemap:
```bash
python3 scripts/gsc_automation.py submit-sitemap
```

Inspect a few key URLs:
```bash
python3 scripts/gsc_automation.py inspect \
  --url https://tsatracker.com/ \
  --url https://tsatracker.com/airports/jfk-tsa-wait-times \
  --url https://tsatracker.com/airports/lga-tsa-wait-times
```

Inspect from a file:
```bash
python3 scripts/gsc_automation.py inspect --urls-file urls.txt
```

### Notes
- This script uses the official `sitemaps.submit` and `urlInspection.index.inspect` APIs.
- It does **not** automate normal `Request indexing`; Google does not expose that as a general API for these pages.

---

## 🔬 Pipeline
Airports currently under research for future integration:
- **ATL**, **DEN**, **SFO**, **IAH**, **LAS**, **BWI**, **DTW**, **IAD**, **DCA**.

Detailed research logs for these can be found in `airport_research/pipeline/`.
