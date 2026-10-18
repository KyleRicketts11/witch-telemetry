"""WITCH - Research Telemetry Command Center.

A Streamlit dashboard for real-time visualization of research telemetry:
- Interactive Plotly charts for token usage and error frequencies
- Raw log viewer for recent .jsonl entries
- Metric summaries for simulation health and convergence rates

Data contract: the dashboard reads newline-delimited JSON (.jsonl). Each line
is one event with a "ts" (ISO 8601 timestamp) and a "type":

  {"ts": "...", "type": "token_usage", "agent": "witch",
   "direction": "in", "tokens": 512, "model": "ilands-1", "session": "abc"}
  {"ts": "...", "type": "error", "error_type": "timeout",
   "message": "...", "severity": "warning"}
  {"ts": "...", "type": "metric", "name": "health_score", "value": 97.2}
  {"ts": "...", "type": "metric", "name": "convergence_rate", "value": 0.83}
  {"ts": "...", "type": "log", "level": "INFO", "source": "runner",
   "message": "..."}

Run with:  streamlit run app.py
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.error import URLError
from urllib.request import urlopen

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DEFAULT_DATA_FILE = os.environ.get("WITCH_TELEMETRY_FILE") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "telemetry.jsonl"
)
# WITCH_TELEMETRY_FILE may be a local path or an http(s) URL to a .jsonl feed.

st.set_page_config(
    page_title="WITCH - Telemetry Command Center",
    page_icon="\U0001f9d9\u200d\u2640\ufe0f",
    layout="wide",
)

# ----------------------------------------------------------------------------
# Data loading
# ----------------------------------------------------------------------------

def _read_lines(path):
    """Read lines from a local .jsonl path or an http(s) URL. Returns (lines, is_url)."""
    if path.startswith(("http://", "https://")):
        with urlopen(path, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace").splitlines(), True
    with open(path, "r", encoding="utf-8") as f:
        return f.read().splitlines(), False


def load_events(path, hours):
    """Read .jsonl telemetry, return (dataframe, skipped_count, source_mtime)."""
    is_url = path.startswith(("http://", "https://"))
    if not is_url and not os.path.exists(path):
        return None, 0, None
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows, skipped = [], 0
    try:
        lines, _ = _read_lines(path)
    except (OSError, URLError):
        return None, 0, None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            ts = pd.to_datetime(obj.get("ts"), utc=True)
            if pd.isna(ts) or ts < cutoff:
                continue
            obj["ts"] = ts
            rows.append(obj)
        except (json.JSONDecodeError, ValueError, TypeError):
            skipped += 1
    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    if is_url:
        mtime = datetime.now(timezone.utc)
    else:
        mtime = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
    return df, skipped, mtime


# ----------------------------------------------------------------------------
# Sidebar controls
# ----------------------------------------------------------------------------

st.sidebar.title("\U0001f9d9\u200d\u2640\ufe0f Command")
data_file = st.sidebar.text_input("Telemetry file (.jsonl)", value=DEFAULT_DATA_FILE)
hours = st.sidebar.slider("Time window (hours)", 1, 72, 12)
auto_refresh = st.sidebar.checkbox("Auto-refresh", value=True)
refresh_secs = st.sidebar.slider("Refresh every (seconds)", 5, 120, 30)
if os.environ.get("WITCH_TELEMETRY_NO_REFRESH"):
    auto_refresh = False  # headless/test mode: never loop

if st.sidebar.button("Generate sample telemetry"):
    import subprocess, sys
    gen = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate_sample_telemetry.py")
    subprocess.run([sys.executable, gen, "--output", data_file], check=False)
    st.sidebar.success("Sample telemetry written.")
    st.rerun()

# ----------------------------------------------------------------------------
# Header
# ----------------------------------------------------------------------------

st.title("\U0001f9d9\u200d\u2640\ufe0f WITCH \u2014 Research Telemetry Command Center")
st.caption("Real-time command and visualization center \u00b7 token usage \u00b7 errors \u00b7 simulation health")

df, skipped, mtime = load_events(data_file, hours)

if df is None:
    st.warning(
        f"No telemetry file found at `{data_file}`. "
        "Click **Generate sample telemetry** in the sidebar to create one, "
        "or point the path above at a real `.jsonl` feed."
    )
    st.stop()

if df.empty:
    st.info(f"No events in the last {hours}h in `{data_file}`. Widen the time window or generate sample data.")
    st.stop()

if skipped:
    st.caption(f"Skipped {skipped} malformed line(s).")

df = df.sort_values("ts").reset_index(drop=True)
st.caption(
    f"Source: `{data_file}` \u00b7 {len(df):,} events in window \u00b7 "
    f"last write {mtime.strftime('%H:%M:%S UTC') if mtime else 'unknown'}"
)

# ----------------------------------------------------------------------------
# Metric summaries
# ----------------------------------------------------------------------------

st.subheader("Simulation health")

metrics = df[df["type"] == "metric"].copy()
tokens = df[df["type"] == "token_usage"].copy()
errors = df[df["type"] == "error"].copy()

def latest_metric(name):
    m = metrics[metrics["name"] == name].sort_values("ts")
    if m.empty:
        return None, None
    vals = m["value"].tolist()
    return vals[-1], (vals[-1] - vals[-2] if len(vals) > 1 else 0.0)

health, health_d = latest_metric("health_score")
conv, conv_d = latest_metric("convergence_rate")

total_tokens = int(tokens["tokens"].sum()) if not tokens.empty and "tokens" in tokens else 0
err_count = len(errors)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Simulation health", f"{health:.1f} / 100" if health is not None else "n/a",
          delta=f"{health_d:+.1f}" if health_d else None)
c2.metric("Convergence rate", f"{conv:.2%}" if conv is not None else "n/a",
          delta=f"{conv_d:+.2%}" if conv_d else None)
c3.metric(f"Tokens (last {hours}h)", f"{total_tokens:,}")
c4.metric(f"Errors (last {hours}h)", f"{err_count:,}",
          delta=None if err_count == 0 else f"{err_count} to inspect",
          delta_color="inverse" if err_count else "normal")

# ----------------------------------------------------------------------------
# Token usage chart
# ----------------------------------------------------------------------------

st.subheader("Token usage")

if not tokens.empty and "tokens" in tokens:
    t = tokens.copy()
    t["direction"] = t.get("direction", "in").fillna("in")
    t["tokens"] = pd.to_numeric(t["tokens"], errors="coerce").fillna(0)
    t = t.set_index("ts").groupby("direction")["tokens"].resample("5min").sum().reset_index()

    fig = go.Figure()
    colors = {"in": "#a855f7", "out": "#22d3ee"}
    for direction in ["in", "out"]:
        d = t[t["direction"] == direction]
        fig.add_trace(go.Scatter(
            x=d["ts"], y=d["tokens"], name=f"tokens {direction}",
            mode="lines", stackgroup="one",
            line=dict(color=colors.get(direction, "#888"), width=1.5),
            fillcolor=colors.get(direction, "#888"),
        ))
    fig.update_layout(
        xaxis_title="Time (UTC)", yaxis_title="Tokens / 5 min",
        hovermode="x unified", height=320, margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

    by_agent = tokens.groupby(tokens.get("agent", "unknown"))["tokens"].sum().sort_values(ascending=False)
    if not by_agent.empty:
        fig2 = px.bar(x=by_agent.index, y=by_agent.values,
                      labels={"x": "Agent", "y": "Tokens"},
                      color_discrete_sequence=["#a855f7"])
        fig2.update_layout(height=260, margin=dict(l=10, r=10, t=30, b=10),
                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("No token_usage events in this window.")

# ----------------------------------------------------------------------------
# Error frequency charts
# ----------------------------------------------------------------------------

st.subheader("Error frequencies")

if not errors.empty:
    e = errors.copy()
    e["error_type"] = e.get("error_type", "unknown").fillna("unknown")

    freq = e["error_type"].value_counts().reset_index()
    freq.columns = ["error_type", "count"]
    fig3 = px.bar(freq, x="error_type", y="count", color="error_type",
                  color_discrete_sequence=px.colors.qualitative.Set2,
                  labels={"error_type": "Error type", "count": "Count"})
    fig3.update_layout(height=280, showlegend=False, margin=dict(l=10, r=10, t=30, b=10),
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig3, use_container_width=True)

    over_time = e.set_index("ts").resample("15min").size().reset_index(name="count")
    fig4 = px.line(over_time, x="ts", y="count", markers=True,
                   labels={"ts": "Time (UTC)", "count": "Errors / 15 min"},
                   color_discrete_sequence=["#f87171"])
    fig4.update_layout(height=260, margin=dict(l=10, r=10, t=30, b=10),
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig4, use_container_width=True)
else:
    st.success("No errors recorded in this window. Clean cauldron.")

# ----------------------------------------------------------------------------
# Raw log viewer
# ----------------------------------------------------------------------------

st.subheader("Raw log viewer")

logs = df[df["type"] == "log"].copy()
col_a, col_b, col_c = st.columns([2, 2, 3])
with col_a:
    levels = sorted(logs.get("level", pd.Series(dtype=str)).dropna().unique().tolist()) if not logs.empty else []
    chosen_levels = st.multiselect("Level", levels, default=levels)
with col_b:
    tail_n = st.selectbox("Show last N entries", [50, 100, 200, 500], index=2)
with col_c:
    query = st.text_input("Search message text", value="")

view = logs
if not logs.empty:
    if chosen_levels:
        view = view[view["level"].isin(chosen_levels)]
    if query:
        view = view[view["message"].astype(str).str.contains(query, case=False, na=False)]
    view = view.sort_values("ts", ascending=False).head(tail_n)

    st.dataframe(
        view[["ts", "level", "source", "message"]].rename(
            columns={"ts": "Time (UTC)", "level": "Level", "source": "Source", "message": "Message"}),
        use_container_width=True, hide_index=True,
    )

    with st.expander(f"Inspect raw JSON ({len(view)} entries)"):
        for _, row in view.head(50).iterrows():
            raw = {k: (v.isoformat() if hasattr(v, "isoformat") else v)
                   for k, v in row.items() if pd.notna(v)}
            st.code(json.dumps(raw, indent=2, default=str), language="json")
else:
    st.info("No log entries in this window.")

# ----------------------------------------------------------------------------
# Auto-refresh
# ----------------------------------------------------------------------------

if auto_refresh:
    time.sleep(refresh_secs)
    st.rerun()
