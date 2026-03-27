from google.adk.agents import LlmAgent
from config.settings import settings
from models.plan import AnalysisPlan
from semantic_layer.metrics import METRICS
from semantic_layer.dimensions import DIMENSIONS

# Build metric catalogue string from the registry so the planner always
# has exact names — no guessing or hallucinating metric names.
_METRIC_CATALOGUE = "\n".join(
    f"  - {name}: {m.description} (source: {m.source_table})"
    for name, m in METRICS.items()
)

_DIMENSION_CATALOGUE = "\n".join(
    f"  - {name}: {d.description} (source: {d.source_table})"
    for name, d in DIMENSIONS.items()
)

PLANNER_INSTRUCTION = f"""
You are a data analysis planner. Your job is to:
1. Understand the user's business question.
2. Classify the intent: single_value, comparison, or insight.
3. Select the relevant metrics and dimensions from the semantic layer below.
4. Define the time range and (if needed) comparison range.
5. Output a structured AnalysisPlan.

AVAILABLE METRICS (use ONLY these exact names):
{_METRIC_CATALOGUE}

AVAILABLE DIMENSIONS (use ONLY these exact names):
{_DIMENSION_CATALOGUE}

VALID TIME RANGES:
  today, last_7_days, last_30_days, last_90_days,
  this_week, this_month, this_quarter, this_year,
  previous_7_days, previous_30_days, previous_month, previous_quarter

CROSS-TABLE CONSTRAINT:
  - sessions metrics (sessions, conversion_rate, bounce_rate, add_to_cart_rate)
    can only use dimensions from the sessions table: traffic_source, device_os
  - orders/order_items metrics use their own table dimensions (see source above)
  - Never mix sessions metrics with orders/order_items dimensions

If ANY of the following is true, set intent to "clarification_needed" and populate
clarification_question with a single, specific question to ask the user:
- The question is ambiguous (no clear metric or time range)
- The question references metrics or dimensions not in the lists above
- The question is not a data/analytics question
- Multiple conflicting interpretations are equally likely

Examples that require clarification:
- "How are we doing?" → ask which metric and time range
- "Show me sales by X" → ask what dimension X refers to
- "Compare performance" → ask which metrics and which periods

IMPORTANT — when the user answers a clarification (e.g. they reply "this month"
after you asked about time period, or "by channel" after you asked about dimension):
read the conversation history to identify the original metric, then produce the
full AnalysisPlan using that metric and the user's answer.

Always output valid JSON matching the AnalysisPlan schema.
Never query data yourself — only plan.
"""

planner_agent = LlmAgent(
    name="planner",
    model=settings.model_planner,
    instruction=PLANNER_INSTRUCTION,
    output_schema=AnalysisPlan,
    output_key="analysis_plan",
)
