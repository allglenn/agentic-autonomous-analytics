from google.adk.agents import LlmAgent
from config.settings import settings
from config.guardrails import guardrails
from tools import run_query, compare_periods, drill_down, list_metrics, list_dimensions

EXECUTOR_INSTRUCTION = f"""
You are a data analysis executor. You follow a ReAct reasoning loop:
  Thought → Action → Observation → Thought → ...

You have access to the following tools:
- list_metrics(): discover available metrics
- list_dimensions(): discover available dimensions
- run_query(metric, dimensions, time_range): fetch a metric
- compare_periods(metric, dimensions, period_1, period_2): compare two periods
- drill_down(metric, current_dimensions, new_dimension, time_range): segment deeper

Rules:
- Never write SQL directly. Use the tools only.
- Stop when the success criteria from the plan is met.
- Maximum {guardrails.max_executor_steps} steps — be efficient.
- Do not expose PII dimensions.
"""

executor_agent = LlmAgent(
    name="executor",
    model=settings.model_name,
    instruction=EXECUTOR_INSTRUCTION,
    tools=[run_query, compare_periods, drill_down, list_metrics, list_dimensions],
    output_key="draft_answer",
)
