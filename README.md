# WITCH — Research Telemetry Command Center

A Streamlit dashboard for real-time visualization of research telemetry, built for
WITCH (Kyle's iLands agent). Kept separate from Kyle's personal dashboard.

## What it shows

- **Metric summaries** — current simulation health score and convergence rate (with deltas), total tokens and error counts in the window
- **Interactive Plotly charts** — token usage over time (in vs. out, stacked) and per-agent totals; error frequency by type and errors over time
- **Raw log viewer** — newest-first table of `.jsonl` log entries with level filter, text search, and expandable raw JSON per entry
- **Auto-refresh** — sidebar toggle, re-reads the `.jsonl` file every N seconds for a live view

## Quick start

```bash
cd ~/workspace/witch-telemetry
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python generate_sample_telemetry.py   # creates telemetry.jsonl with sample data
.venv/bin/streamlit run app.py
```

Then open the URL Streamlit prints (usually http://localhost:8501).

## Feeding it real telemetry

Point the **"Telemetry file (.jsonl)"** field in the sidebar at any newline-delimited
JSON file — a local path or an `http(s)` URL to a `.jsonl` feed.

On Streamlit Cloud (or any host), set the `WITCH_TELEMETRY_FILE` environment
variable to the telemetry location instead of typing it in the sidebar. The app
reads it at startup; the sidebar field still lets you override it live.

```json
{"ts": "2026-10-18T12:00:00+00:00", "type": "token_usage", "agent": "witch", "direction": "in", "tokens": 512, "model": "ilands-1", "session": "sess-001"}
{"ts": "2026-10-18T12:01:00+00:00", "type": "error", "error_type": "timeout", "message": "Upstream inference timeout", "severity": "warning"}
{"ts": "2026-10-18T12:02:00+00:00", "type": "metric", "name": "health_score", "value": 97.2}
{"ts": "2026-10-18T12:02:00+00:00", "type": "metric", "name": "convergence_rate", "value": 0.83}
{"ts": "2026-10-18T12:03:00+00:00", "type": "log", "level": "INFO", "source": "runner", "message": "Step 42 complete"}
```

Event types: `token_usage` (needs `tokens`, `direction` in/out), `error` (needs
`error_type`), `metric` (`name` = `health_score` or `convergence_rate`), `log`
(`level`, `source`, `message`). Malformed lines are skipped and counted.

## Files

- `app.py` — the dashboard
- `generate_sample_telemetry.py` — sample data generator
- `telemetry.jsonl` — sample data (regenerate anytime from the sidebar)
- `.streamlit/config.toml` — dark witchy theme
