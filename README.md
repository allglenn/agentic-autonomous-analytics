# AI Data Analyst Agent

## BigQuery + Semantic Layer + Google ADK 1.27.4

An agentic AI system that explores business data using natural language, powered by:

- **Google ADK 1.27.4** — Agent orchestration (`LlmAgent`, `LoopAgent`, `SequentialAgent`, `BaseAgent`)
- **BigQuery** — Cloud data warehouse
- **Semantic Layer** — No raw SQL in agents, metric abstraction layer
- **ReAct Reasoning** — Thought → Action → Observation (enforced by `LoopAgent`)
- **Planner → Executor → CriticGate** — ADK-native multi-agent pipeline
- **PostgreSQL** — ADK session execution state + self-managed conversations & messages tables

![Platform screenshot](v1.png)

---

## Core Concepts

### 1. Planner Agent

Responsible for:

- Understanding user intent
- Selecting metrics and dimensions
- Defining analysis strategy

Example output:

```json
{
  "intent": "insight",
  "metrics": ["revenue"],
  "time_range": "last_7_days",
  "comparison_range": "previous_7_days",
  "dimensions": ["channel"],
  "drilldown_path": ["campaign"],
  "success_criteria": "identify cause of drop"
}
```

### 2. Executor Agent (ReAct Loop)

Executes the plan using iterative reasoning:

```text
Thought → Action → Observation → Thought → ...
```

Capabilities:

- Run queries
- Compare periods
- Drill down across dimensions
- Detect anomalies

### 3. CriticGate (BaseAgent)

A custom ADK `BaseAgent` — not optional, always runs after the executor.

Validates:

- Correctness of conclusions
- Completeness of analysis
- Alignment with data

On `validated=True` → yields `Event(escalate=True)` to break the `analysis_loop`.
On `validated=False` → writes `critic_notes` to session state for the executor to retry.

### 4. Semantic Layer

The agent never writes SQL directly. Instead:

```python
run_query(metric="revenue", dimensions=["channel"])
```

Is translated internally to:

```sql
SELECT channel, SUM(amount) AS revenue
FROM orders
GROUP BY channel
```

---

## Available Tools

| Tool | Description |
| ---- | ----------- |
| `run_query(metric, dimensions, time_range)` | Execute a metric query via the semantic layer |
| `compare_periods(metric, dimensions, period_1, period_2)` | Compare a metric across two time periods |
| `drill_down(metric, current_dimensions, new_dimension, time_range)` | Segment deeper by adding a dimension |
| `decompose(metric, dimension, period_1, period_2)` | Show which segments drove a change — per-segment delta and % contribution to total change |
| `correlate(metric_a, metric_b, dimension, time_range)` | Pearson correlation between two metrics across a shared dimension (e.g. do channels with more sessions also generate more revenue?) |
| `list_metrics()` | List all available metrics |
| `list_dimensions()` | List all available dimensions (PII excluded) |

### Correlational Analytics (v1)

The `decompose` and `correlate` tools provide richer context beyond single-number answers, without requiring additional data sources:

- **`decompose`** — answers "what drove the change?" by computing each segment's absolute delta and % contribution to a period-over-period shift. Example: *"Which channels drove the revenue decline this quarter?"*
- **`correlate`** — answers "are these two things related?" using Pearson correlation across dimension segments. Example: *"Do channels with more sessions also generate more orders?"*

> **Limitation**: these tools measure correlation, not causation. True causal inference requires experimental data (A/B tests), marketing spend tables, or counterfactual models — planned for a future milestone.

---

## Semantic Layer — Ecommerce Model

The agent never writes SQL. All queries go through the semantic layer which resolves metrics and dimensions to their source tables.

### Metrics (17)

| Group | Metrics | Source Table |
| ----- | ------- | ------------ |
| Revenue | `revenue`, `net_revenue`, `refund_amount`, `shipping_cost` | `orders` |
| Orders | `orders`, `average_order_value`, `cancellation_rate`, `refund_rate` | `orders` |
| Customers | `new_customers`, `repeat_customers`, `unique_customers` | `orders` |
| Products | `units_sold`, `items_per_order` | `order_items` |
| Traffic | `sessions`, `conversion_rate`, `bounce_rate`, `add_to_cart_rate` | `sessions` |

### Dimensions (21)

| Group | Dimensions |
| ----- | ---------- |
| Channel | `channel`, `traffic_source`, `campaign`, `utm_medium` |
| Geography | `country`, `region`, `city` |
| Product | `product_category`, `brand`, `product_name` |
| Customer | `customer_segment`, `customer_type` |
| Device | `device`, `device_os` |
| Time | `day`, `week`, `month` |
| Promotion | `promotion_code`, `discount_type` |
| Order | `order_status`, `payment_method` |

### Time Ranges (12)

`today` · `last_7_days` · `last_30_days` · `last_90_days` · `this_week` · `this_month` · `this_quarter` · `this_year` · `previous_7_days` · `previous_30_days` · `previous_month` · `previous_quarter`

### Alias Normalisation

The resolver automatically maps common LLM aliases to canonical names so the agent never errors on reasonable variants:

| LLM may say | Resolves to |
| ----------- | ----------- |
| `marketing_channel`, `channel_name` | `channel` |
| `device_type`, `platform` | `device` |
| `shipping_country` | `country` |
| `status`, `order_status_name` | `order_status` |
| `coupon_code`, `coupon` | `promotion_code` |
| `last_week`, `past_week` | `last_7_days` |
| `previous_week` | `previous_7_days` |
| `last_month`, `past_month` | `last_30_days` |

### PII Protection

The following fields are permanently blocked from the agent:
`user_id` · `customer_id` · `email` · `phone` · `ip_address` · `full_name` · `address`

---

## Supported Analysis Types

### Single Value

```text
"What is revenue today?"
```

→ single query against `orders`

### Comparison

```text
"Compare conversion_rate this month vs last month by device"
```

→ two queries against `sessions` + delta

### Insight / Root Cause

```text
"Why did revenue drop last week?"
```

→ iterative:

1. Detect drop — `revenue` over `last_7_days` vs `previous_7_days`
2. Segment — by `channel`, `country`, `product_category`
3. Drill down — by `campaign`, `brand`
4. Identify root cause

---

## Architecture

```mermaid
flowchart TD

    %% ---------------- CONVERSATION STORE ----------------
    DB[(PostgreSQL<br/>conversations · messages)]

    %% ---------------- USER ----------------
    A[User Question] --> PRE[Fetch prior messages<br/>from messages table]
    PRE --> DB
    DB -->|last 6 turns| B

    %% ---------------- PLANNER ----------------
    B[Planner Agent<br/>LlmAgent · gemini-2.5-pro<br/>question + conversation context]

    B --> C[LLM Reasoning<br/>Classify intent + metrics + dimensions]

    C --> CL{Intent Clear?}

    %% ---------------- CLARIFICATION SHORTCUT ----------------
    CL -->|No| CLQ[Clarification Question<br/>Ask user to refine]
    CLQ --> SAVECL[Save Q&A to messages table]
    SAVECL --> DB
    SAVECL --> AA

    %% ---------------- ANALYSIS PATH ----------------
    CL -->|Yes| D{Intent Type}

    D -->|Single Value| E[Plan: 1 step query]
    D -->|Comparison| F[Plan: Multi-query comparison]
    D -->|Insight / Root Cause| G[Plan: Iterative drill-down]

    E --> H[Structured Analysis Plan]
    F --> H
    G --> H

    %% ---------------- FRESH ADK SESSION PER REQUEST ----------------
    H --> HS[Fresh ADK Session<br/>state.analysis_plan injected]

    %% ---------------- OUTER LOOP ----------------
    HS --> AL[analysis_loop<br/>LoopAgent · max 3 retries]

    %% ---------------- EXECUTOR — INNER LOOP ----------------
    AL --> I[executor_agent<br/>LoopAgent · max 10 steps]

    I --> IR[Read state.analysis_plan<br/>+ state.critic_notes if retry]

    IR --> K[LlmAgent Thought<br/>gemini-2.5-flash · select next step]

    K --> L{Action Type}

    L -->|Fetch Metric| M[run_query]
    L -->|Compare| N[compare_periods]
    L -->|Drill Down| O[drill_down]
    L -->|Decompose| O2[decompose]
    L -->|Correlate| O3[correlate]

    %% ---------------- TOOL LAYER ----------------
    M --> P[Semantic Layer<br/>Resolve metric → SQL]
    N --> P
    O --> P
    O2 --> P
    O3 --> P

    P --> Q[BigQuery Execution<br/>asyncio.wait_for · 30s timeout]

    Q --> R[Observation · Query Result]

    %% ---------------- REACT LOOP CONTROL ----------------
    R --> S{Success Criteria Met?}

    S -->|No| T[Refine / Drill deeper]
    T --> K

    S -->|Yes| U[Synthesize Findings]

    U --> V[(state.draft_answer)]

    %% ---------------- CRITIC GATE ----------------
    V --> W[CriticGate<br/>BaseAgent]

    W --> WL[LlmAgent · gemini-2.5-pro<br/>Validate correctness + completeness]

    WL --> X{validated?}

    X -->|No| XN[(state.critic_notes<br/>feedback for next retry)]
    XN --> AL

    X -->|Yes| XY[escalate=True<br/>Break analysis_loop]

    XY --> Z[Parse FinalAnswer JSON<br/>summary · findings · evidence · confidence]

    %% ---------------- SAVE & RESPOND ----------------
    Z --> SAVE[Save summary to messages table]
    SAVE --> DB
    SAVE --> AA[Return structured FinalAnswer to User]
```

### How to Read This Diagram

#### 1. Conversation Store (PostgreSQL)

All user questions and final answers are stored in a self-managed `messages` table.
The last 6 messages are fetched before each planner call so follow-up questions
("last month", "that metric", "yes") resolve correctly against prior turns.

#### 2. Planner (top)

- Receives the current question **plus conversation history** as context
- Classifies the request and builds a structured execution plan
- Decides the analysis path: single value / comparison / insight
- If the intent is ambiguous → returns a **clarification question**, saves the exchange to the messages table, and skips the executor

#### 3. Fresh ADK Session per Request

A new ADK session is created for every request with the `analysis_plan` injected as initial state.
This prevents old tool results from prior turns bleeding into the new execution context.
Conversation memory is provided by the messages table, not by ADK session history.

#### 4. analysis_loop — Outer LoopAgent (max 3 retries)

Wraps the Executor and CriticGate. Each iteration is one full attempt:
Executor runs → Critic validates → retry if needed.
Stops when `CriticGate` escalates (`validated=True`) or retries are exhausted.

#### 5. Executor — Inner ReAct LoopAgent (max 10 steps)

The core reasoning engine (`gemini-2.5-flash`):

```text
Thought → Action → Observation → Thought → ...
```

- Reads `state.analysis_plan` (from Planner) and `state.critic_notes` (from previous retry)
- Keeps querying and drilling down until success criteria are met
- Writes `state.draft_answer` when done

#### 6. Tool Layer — Semantic Abstraction

- The Semantic Layer translates metric requests into SQL
- BigQuery executes the query via `asyncio.wait_for` with a hard 30s timeout
- The agent never writes or touches raw SQL directly

#### 7. CriticGate — Custom BaseAgent (bottom)

- Runs the critic `LlmAgent` (`gemini-2.5-pro`) to validate correctness and completeness
- `validated=True` → yields `Event(escalate=True)` → `analysis_loop` stops
- `validated=False` → writes `critic_notes` to state → loop retries with executor

#### 8. FinalAnswer & Response

The `FinalAnswer` JSON (summary, findings, evidence, confidence, validated) is parsed from the last ADK event.
Only the `summary` is saved to the messages table for clean history.
The full structured object is returned to the frontend for rich display.

---

## Tech Stack

| Technology         | Purpose                                                      |
| ------------------ | ------------------------------------------------------------ |
| Google ADK 1.27.4  | Agent orchestration (`LlmAgent`, `LoopAgent`…)               |
| Gemini 2.5 Pro     | Planner + Critic reasoning                                   |
| Gemini 2.5 Flash   | Executor tool-call loop                                      |
| BigQuery           | Cloud data warehouse                                         |
| Semantic Layer     | Metric abstraction — no raw SQL in agents                    |
| PostgreSQL         | ADK session state + conversations & messages tables          |
| Python / FastAPI   | Backend + REST API                                           |
| Next.js 14         | Chat frontend (port 3000)                                    |
| Docker / Cloud Run | Containerised deployment                                     |

---

## Project Structure

```text
Agentic_aut/
├── agents/
│   ├── planner.py             # LlmAgent — classifies intent, outputs AnalysisPlan
│   ├── executor.py            # LoopAgent wrapping LlmAgent — ReAct tool-call loop
│   └── critic.py              # CriticGate (BaseAgent) — validates, escalates on success
│
├── tools/                     # ADK tool functions (no SQL, semantic layer only)
│   ├── run_query.py           # execute_sql_async — hard 30s asyncio timeout
│   ├── compare_periods.py     # two parallel queries via asyncio.gather
│   ├── drill_down.py
│   ├── decompose.py           # per-segment delta + % contribution between periods
│   ├── correlate.py           # Pearson correlation between two metrics by dimension
│   ├── list_metrics.py
│   └── list_dimensions.py
│
├── semantic_layer/            # Metric/dimension registry — agents never touch SQL
│   ├── metrics.py
│   ├── dimensions.py
│   └── resolver.py            # Translates metric + dims → BigQuery SQL
│
├── bigquery/
│   ├── client.py              # Singleton BQ client (emulator-aware)
│   └── executor.py            # execute_sql (sync) + execute_sql_async (wait_for wrapper)
│
├── orchestrator/
│   ├── pipeline.py            # analysis_loop LoopAgent (executor + critic)
│   └── planner_runner.py      # run_planner(question, history) — fresh session per call
│
├── api/
│   ├── main.py                # FastAPI app + lifespan (init_db, auto-seed BQ emulator)
│   └── routes.py              # POST /ask · GET|DELETE|PATCH /sessions · GET /sessions/{id}/messages
│
├── db/
│   └── conversations.py       # conversations + messages tables (SQLAlchemy async)
│
├── models/                    # Pydantic schemas shared across all layers
│   ├── plan.py                # AnalysisPlan, IntentType (incl. clarification_needed)
│   ├── query.py               # QueryRequest, QueryResult
│   └── answer.py              # DraftAnswer, FinalAnswer
│
├── config/
│   ├── settings.py            # Env vars via pydantic-settings
│   ├── guardrails.py          # Metric allowlist, max_steps, PII rules
│   └── session.py             # Shared DatabaseSessionService (PostgreSQL)
│
├── tests/
│   ├── test_semantic_layer.py
│   └── test_guardrails.py
│
├── frontend/                  # Next.js 14 chat interface (port 3000)
│   ├── app/
│   │   ├── api/ask/route.ts          # Proxy → FastAPI /ask
│   │   ├── api/sessions/route.ts     # GET /api/sessions (force-dynamic)
│   │   ├── api/sessions/[id]/route.ts # GET · DELETE · PATCH per session
│   │   ├── page.tsx                  # Chat UI — FinalAnswer structured card renderer
│   │   └── layout.tsx
│   └── components/
│       └── Sidebar.tsx               # Conversation history sidebar
│
├── scripts/
│   └── seed_data.py           # Generates orders, order_items (with created_at), sessions
│
├── main.py                    # CLI entrypoint (asyncio, InMemory sessions)
├── docker-compose.yml         # API + PostgreSQL + BigQuery emulator + frontend
├── Makefile                   # venv, run, dev, seed, test, docker shortcuts
├── requirements.txt
├── .env.example
└── Dockerfile
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Google API key (Gemini access)
- Google Cloud project with BigQuery enabled
- Docker (for PostgreSQL session store)

### Installation

```bash
git clone https://github.com/allglenn/agentic-autonomous-analytics.git
cd agentic-autonomous-analytics
make venv
source .venv/bin/activate
make install
```

### Configuration

```bash
cp .env.example .env
```

```env
GOOGLE_API_KEY=your-google-api-key
GOOGLE_GENAI_API_KEY=your-google-genai-api-key
BIGQUERY_DATASET=analytics
MODEL_PLANNER=gemini-2.5-pro
MODEL_EXECUTOR=gemini-2.5-flash
MODEL_CRITIC=gemini-2.5-pro
DATABASE_URL=postgresql+asyncpg://adk:adk@localhost:5432/adk_sessions
```

### Seed the Dataset

The seed script generates realistic ecommerce data (orders, order items, sessions) and loads it into BigQuery.

**With the local emulator (recommended for dev):**

```bash
make docker-up   # starts BigQuery emulator + PostgreSQL
make seed        # loads 1 000 orders (default)
make seed-large  # loads 5 000 orders
```

**With real GCP BigQuery:**

```bash
# set GOOGLE_CLOUD_PROJECT in .env, then:
python3 scripts/seed_data.py --orders 1000
```

**What gets generated:**

| Table | Rows (default) | Description |
| ----- | -------------- | ----------- |
| `orders` | 1 000 | Orders with channel, status, payment, geography, discount |
| `order_items` | ~3 067 | Line items per order with product, brand, category, price, created_at |
| `sessions` | 3 500 | Web sessions — 1 000 converted, 2 500 non-converted |

All columns match the semantic layer schema so every metric and dimension works immediately after seeding.

---

### Run — Docker (API + PostgreSQL)

```bash
make docker-up
```

### Run — Local API (requires PostgreSQL running)

```bash
make dev
```

```bash
curl -X POST http://localhost:8080/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Why did revenue drop last week?"}'
```

### Run — CLI

```bash
make run
```

```text
> Why did revenue drop last week?
```

---

## Example Questions — Full Pipeline Coverage

These questions are designed to exercise every path in the architecture diagram. Run them after seeding to validate the full system end-to-end.

### Path 1 — Single Value (one query, one metric)

- What is the total revenue for the last 30 days?
- How many orders were placed this month?
- What is the current conversion rate?
- How many new customers did we acquire last week?
- What is the average order value this quarter?

### Path 2 — Comparison (two periods + delta)

- Compare revenue this month vs last month.
- How did conversion rate change between last 7 days and the previous 7 days?
- Compare average order value this month vs last month by channel.
- Did refund rate go up or down compared to last month?
- Compare units sold by product category this quarter vs last quarter.

### Path 3 — Insight / Root Cause (iterative drill-down loop)

- Why did revenue drop last week?
- Why is the cancellation rate so high this month?
- Which channel is driving the most new customers this quarter and why?
- Why is the conversion rate lower on mobile than desktop?
- What is causing the bounce rate spike in the last 7 days?

### Path 4 — Clarification (ambiguous intent → agent asks before executing)

- Show me the data.
- What happened last week?
- Is performance good?
- Tell me about our customers.

### Cross-Table Drill-Down (uses `drill_down` tool across tables)

- What are the top product categories by revenue this month?
- Which brands have the highest refund rate this quarter?
- What is the revenue breakdown by channel and customer segment?
- Which payment methods are most popular among VIP customers?
- What is the add_to_cart rate by device type over the last 30 days?

---

## Guardrails

| Guardrail | Description |
| --------- | ----------- |
| Metric allowlist | Restrict which metrics the agent is permitted to query |
| Query size limit | Cap result set size to control BigQuery costs |
| Max steps | Hard limit on Executor loop iterations to prevent runaway analysis |
| PII protection | Block dimensions or fields that could expose personal data |

---

## Roadmap

- [ ] Add caching layer (Redis / Firestore)
- [x] Add memory (conversation context via messages table)
- [ ] Add alerting (proactive insights)
- [ ] Add dashboard integration (Looker / Streamlit)
- [ ] Multi-tenant SaaS support

---

## Why This Project Matters

This system is essentially an **AI Data Analyst on top of your data warehouse** — combining:

- **Semantic understanding** — knows your business metrics, not just SQL
- **Autonomous reasoning** — iterates until it finds the real answer
- **Structured analysis** — every step is traceable and explainable

---

## Future Improvements

- Multi-agent collaboration (dedicated planner / analyst / critic agents)
- Cost-aware query planning
- Anomaly detection models
- Auto-generated dashboards

---

## Author

Built by an engineer focused on AI agents, SaaS systems, and data-driven automation.

---

## License

This project is licensed under the MIT License.
