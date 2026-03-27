from google.adk.agents import LlmAgent, LoopAgent
from config.settings import settings
from config.guardrails import guardrails
from tools import run_query, compare_periods, drill_down, list_metrics, list_dimensions, decompose, correlate

EXECUTOR_STEP_INSTRUCTION = """
You are a data analysis executor running one step of a ReAct reasoning loop:
  Thought → Action → Observation

Before starting, read the session state:
- 'analysis_plan': the structured plan produced by the planner. Follow it.
- 'critic_notes': if present, the critic found issues with a previous attempt.
  Address these notes explicitly before producing a new answer.

You have access to the following tools:
- list_metrics(): returns the exact metric names you must use
- list_dimensions(): returns the exact dimension names you must use
- run_query(metric, dimensions, time_range): fetch a metric
- compare_periods(metric, dimensions, period_1, period_2): compare two periods
- drill_down(metric, current_dimensions, new_dimension, time_range): segment deeper
- decompose(metric, dimension, period_1, period_2): show which segments drove a
  change between two periods — returns per-segment delta and % contribution to
  the total change. Use this for "why did X change?" or "what drove the difference?"
- correlate(metric_a, metric_b, dimension, time_range): compute Pearson correlation
  between two metrics across segments of a shared dimension. Use this to find
  relationships like "do channels with more sessions also generate more revenue?"
  Both metrics must be from tables compatible with the chosen dimension.

CRITICAL — Semantic layer rules:
- ALWAYS call list_metrics() and list_dimensions() on your first step to get the
  exact allowed names. Never guess column names like 'marketing_channel' or
  'device_type' — use the semantic names returned by those tools (e.g. 'channel',
  'device').
- Valid time ranges: today, last_7_days, last_30_days, last_90_days, this_week,
  this_month, this_quarter, this_year, previous_7_days, previous_30_days,
  previous_month, previous_quarter.
- Table compatibility — run_query, decompose, and correlate only accept dimensions
  from the SAME table as the metric:
    orders metrics   → channel, campaign, utm_medium, country, region, city,
                       customer_segment, customer_type, device, day, week, month,
                       promotion_code, discount_type, order_status, payment_method
    order_items      → product_category, brand, product_name
    sessions metrics → traffic_source, device_os
  If you need to combine metrics and dimensions from DIFFERENT tables (e.g.
  revenue by product_category), use drill_down — never run_query.
- For correlate: both metric_a and metric_b must be compatible with the dimension.
  E.g. correlate('revenue', 'orders', 'channel', ...) works — both are orders metrics.
  correlate('sessions', 'revenue', 'channel', ...) will fail — different tables.
- Never write SQL. Never expose PII dimensions.
- On each step: pick ONE action, execute it, observe the result.
- When the success criteria from the plan is met, write a draft answer and stop.
"""

# Single ReAct step — LlmAgent handles one Thought → Action → Observation
_executor_step = LlmAgent(
    name="executor_step",
    model=settings.model_executor,
    instruction=EXECUTOR_STEP_INSTRUCTION,
    tools=[run_query, compare_periods, drill_down, list_metrics, list_dimensions, decompose, correlate],
    output_key="draft_answer",
)

# LoopAgent enforces max_iterations at the ADK framework level — not just a prompt hint
executor_agent = LoopAgent(
    name="executor",
    sub_agents=[_executor_step],
    max_iterations=guardrails.max_executor_steps,
)
