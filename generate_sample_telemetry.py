"""Generate sample research telemetry as .jsonl for the WITCH dashboard.

Usage:
    python generate_sample_telemetry.py [--output telemetry.jsonl] [--hours 12]

Emits token_usage, error, metric (health_score, convergence_rate), and log
events with realistic structure so the dashboard renders immediately.
"""

import argparse
import json
import random
from datetime import datetime, timedelta, timezone

AGENTS = ["witch", "witch"]
MODELS = ["ilands-1", "ilands-1-lite"]
ERROR_TYPES = [
    ("timeout", "Upstream inference timeout after 30s", "warning"),
    ("rate_limit", "Token budget rate limit hit, backing off", "warning"),
    ("parse_error", "Malformed tool call JSON, retrying", "info"),
    ("context_overflow", "Context window exceeded, compacting", "critical"),
]
LOG_SOURCES = ["runner", "scheduler", "tokenizer", "evaluator"]
LOG_TEMPLATES = [
    ("INFO", "runner", "Simulation step {n} completed in {d:.1f}s"),
    ("INFO", "scheduler", "Queued batch {n} ({k} tasks)"),
    ("INFO", "evaluator", "Convergence delta {d:.4f} within tolerance"),
    ("WARNING", "tokenizer", "Long prompt truncated to {k} tokens"),
    ("DEBUG", "runner", "Checkpoint written: step {n}"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="telemetry.jsonl")
    ap.add_argument("--hours", type=int, default=12)
    args = ap.parse_args()

    random.seed(20261018)
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=args.hours)

    health = 96.0
    conv = 0.42
    events = []

    t = start
    step = 0
    while t < now:
        step += 1
        # token usage: a few bursts per minute
        for _ in range(random.randint(1, 4)):
            direction = random.choice(["in", "in", "out"])
            events.append({
                "ts": (t + timedelta(seconds=random.randint(0, 59))).isoformat(),
                "type": "token_usage",
                "agent": random.choice(AGENTS),
                "direction": direction,
                "tokens": random.randint(80, 2400) if direction == "in" else random.randint(40, 900),
                "model": random.choice(MODELS),
                "session": f"sess-{step // 60:03d}",
            })
        # metrics drift
        health = min(99.5, max(88.0, health + random.uniform(-0.6, 0.5)))
        conv = min(0.985, max(0.30, conv + random.uniform(-0.012, 0.02)))
        if step % 5 == 0:
            events.append({"ts": t.isoformat(), "type": "metric", "name": "health_score",
                           "value": round(health, 2)})
            events.append({"ts": t.isoformat(), "type": "metric", "name": "convergence_rate",
                           "value": round(conv, 4)})
        # occasional errors
        if random.random() < 0.06:
            et, msg, sev = random.choice(ERROR_TYPES)
            events.append({"ts": t.isoformat(), "type": "error", "error_type": et,
                           "message": msg, "severity": sev})
        # logs
        if random.random() < 0.5:
            lvl, src, tmpl = random.choice(LOG_TEMPLATES)
            events.append({"ts": t.isoformat(), "type": "log", "level": lvl, "source": src,
                           "message": tmpl.format(n=step, d=random.uniform(0.4, 3.2),
                                                  k=random.randint(2, 32))})
        t += timedelta(minutes=1)

    events.sort(key=lambda e: e["ts"])
    with open(args.output, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
    print(f"Wrote {len(events)} events to {args.output}")


if __name__ == "__main__":
    main()
