# Proactive Insights — Design & Implementation Plan

## Overview

Instead of waiting for the user to ask a question, the system periodically monitors key metrics, detects anomalies or notable changes, and surfaces them unprompted — directly in the chat UI and optionally via webhook (Slack, email).

The insight engine reuses the existing agent pipeline (Planner → Executor → Critic) as its reasoning core. No new data pipeline is required.

---

## Trigger Strategy

### Automatic Anomaly Detection (Phase 1)

Scan a fixed set of high-priority metrics on a schedule. For each metric, compare the current period against a rolling baseline (same day over the prior N weeks). Fire when the deviation exceeds a configurable threshold.

```python
# Example: revenue today vs average of same day over last 4 weeks
delta_pct = (today - baseline) / baseline * 100
if abs(delta_pct) > THRESHOLD_PCT:
    # surface insight
```

**Watched metrics (default set):**

| Metric | Source Table | Default Threshold |
| --- | --- | --- |
| `revenue` | orders | >10% deviation |
| `orders` | orders | >15% deviation |
| `sessions` | sessions | >20% deviation |
| `conversion_rate` | sessions | >10% deviation |
| `bounce_rate` | sessions | >15% deviation |

### User-Configured Watches (Phase 2)

Users define custom watches on any metric via the UI:

- Metric + dimension breakdown
- Time window (daily, hourly)
- Alert threshold (absolute or percentage)
- Delivery channel (in-app, Slack, email)

Example: *"Alert me if revenue drops more than 10% day-over-day."*

---

## Architecture

```
APScheduler (inside FastAPI lifespan)
    │
    ▼  every N minutes, per watched metric
compare_periods(metric, [], "today", "previous_7_days")   ← existing tool
    │
    ▼  deviation > threshold?
run_planner + analysis_loop                                ← existing pipeline
    │
    ▼
FinalAnswer (summary + findings + evidence + chart)
    │
    ▼
Save to `insights` table (PostgreSQL)
    │
    ├──► Frontend — SSE push / polling via GET /insights
    └──► Webhook — Slack / email HTTP POST
```

The existing `compare_periods`, `decompose`, and `correlate` tools handle the heavy lifting. The agent already knows how to explain *why* a metric changed — the scheduler just needs to trigger it.

---

## New Components

### Backend

| File | Role |
| --- | --- |
| `orchestrator/monitor.py` | Anomaly detection loop — scans metrics, decides if deviation is worth surfacing, triggers the full pipeline |
| `db/insights.py` | `insights` table (SQLAlchemy async) — stores generated insight with `seen` flag, severity, metric, delta |
| `api/routes_insights.py` | `GET /insights` (list unseen), `POST /watches` (user-configured rules), `PATCH /insights/{id}/seen` |
| `config/settings.py` | New env vars: `INSIGHT_SCAN_INTERVAL_MINUTES`, `INSIGHT_THRESHOLD_PCT`, `SLACK_WEBHOOK_URL` |

### Database — `insights` table

```sql
CREATE TABLE insights (
    id          SERIAL PRIMARY KEY,
    metric      VARCHAR(100) NOT NULL,
    delta_pct   FLOAT NOT NULL,
    severity    VARCHAR(20) NOT NULL,   -- 'info' | 'warning' | 'critical'
    summary     TEXT NOT NULL,
    findings    JSONB,
    chart       JSONB,
    seen        BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

### Scheduler — `orchestrator/monitor.py`

```python
async def scan_metrics():
    for metric in WATCHED_METRICS:
        result = await compare_periods(metric, [], "today", "previous_7_days")
        delta_pct = compute_delta(result)

        if abs(delta_pct) < settings.insight_threshold_pct:
            continue

        # Reuse existing pipeline to explain the anomaly
        question = f"Why did {metric} change significantly today?"
        answer = await run_full_pipeline(question)

        severity = classify_severity(delta_pct)
        await save_insight(metric, delta_pct, severity, answer)
        await dispatch_webhooks(metric, delta_pct, severity, answer)
```

Severity classification:

| Delta | Severity |
| --- | --- |
| 10–20% | `info` |
| 20–35% | `warning` |
| >35% | `critical` |

### Frontend

- **Insights badge** on the sidebar — red dot when unseen insights exist
- **Insights feed** — dedicated panel listing cards (metric, delta, summary, optional chart)
- **Mark as seen** — dismiss on open, `PATCH /insights/{id}/seen`
- **"Watch this metric"** button on answer cards — creates a user-defined watch rule

---

## Delivery Channels

### In-App (SSE or polling)

Frontend polls `GET /insights?unseen=true` every 60 seconds, or receives a Server-Sent Event push when a new insight is saved.

### Slack Webhook

```python
async def post_slack(insight: Insight):
    payload = {
        "text": f":rotating_light: *{insight.severity.upper()}* — {insight.metric}",
        "attachments": [{
            "text": insight.summary,
            "color": severity_color(insight.severity),
            "footer": f"Delta: {insight.delta_pct:+.1f}%"
        }]
    }
    await httpx.post(settings.slack_webhook_url, json=payload)
```

### Email (Phase 2)

Daily digest via SendGrid or SMTP — batches all `warning` + `critical` insights from the past 24h.

---

## Configuration (`.env`)

```env
# Proactive Insights
INSIGHT_SCAN_INTERVAL_MINUTES=60
INSIGHT_THRESHOLD_PCT=10
INSIGHT_RETENTION_DAYS=30

# Delivery
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

---

## Phased Rollout

### Phase 1 — Automatic scanner (no user config)

- APScheduler scans the 5 default metrics every 60 minutes
- Anomalies trigger the full Planner → Executor → Critic pipeline
- Results saved to `insights` table
- Frontend polls `GET /insights` and renders a badge + feed

**Deliverables:** `monitor.py`, `db/insights.py`, `routes_insights.py`, frontend badge + feed

### Phase 2 — User-configured watches

- `POST /watches` endpoint — user defines metric, threshold, schedule, channel
- "Watch this metric" button on answer cards
- Slack and email delivery

**Deliverables:** `watches` table, watch UI, webhook dispatcher

### Phase 3 — Statistical baseline (smarter anomaly detection)

- Replace simple period-over-period delta with rolling mean ± N standard deviations
- Reduces false positives on naturally volatile metrics (e.g. sessions on weekends)
- Requires storing a rolling metric history table

---

## Reuse of Existing Infrastructure

| Existing piece | How it's reused |
| --- | --- |
| `compare_periods` tool | Primary anomaly detection signal |
| `decompose` tool | Explains which segments drove the change |
| `run_planner` + `analysis_loop` | Generates the full insight explanation |
| PostgreSQL | `insights` + `watches` tables alongside existing `conversations` / `messages` |
| Redis cache | Query results are cached — repeated scans of the same metric hit cache, not BigQuery |
| `FinalAnswer` schema | Insight answer reuses the same structured response format |
| Chart generator | Charts included in insight cards where applicable |

The entire reasoning engine is already built. Proactive insights add a **scheduler + storage layer on top** — no changes to the agent core.

---

## Open Questions

1. **False positive rate** — how aggressive should the default threshold be? Start at 10% or 20%?
2. **Scan frequency** — hourly is safe for BigQuery cost; sub-hourly needs Redis cache to be active.
3. **Multi-tenant** — when multi-tenant support lands (roadmap), each tenant needs isolated watch rules and insight feeds.
4. **Insight deduplication** — avoid re-surfacing the same anomaly every scan cycle. Needs a cooldown window per metric (e.g. 6h before re-alerting on the same metric).
