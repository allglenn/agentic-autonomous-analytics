from google.adk.agents import LlmAgent, LoopAgent
from config.settings import settings
from config.guardrails import guardrails
from tools import run_query, compare_periods, drill_down, list_metrics, list_dimensions

EXECUTOR_STEP_INSTRUCTION = """
You are a data analysis executor running one step of a ReAct reasoning loop:
  Thought → Action → Observation

You have access to the following tools:
- list_metrics(): discover available metrics
- list_dimensions(): discover available dimensions
- run_query(metric, dimensions, time_range): fetch a metric
- compare_periods(metric, dimensions, period_1, period_2): compare two periods
- drill_down(metric, current_dimensions, new_dimension, time_range): segment deeper

Rules:
- Never write SQL directly. Use the tools only.
- Do not expose PII dimensions.
- On each step: pick ONE action, execute it, observe the result.
- When the success criteria from the plan is met, set output_key and stop.
"""

# Single ReAct step — LlmAgent handles one Thought → Action → Observation
_executor_step = LlmAgent(
    name="executor_step",
    model=settings.model_name,
    instruction=EXECUTOR_STEP_INSTRUCTION,
    tools=[run_query, compare_periods, drill_down, list_metrics, list_dimensions],
    output_key="draft_answer",
)

# LoopAgent enforces max_iterations at the ADK framework level — not just a prompt hint
executor_agent = LoopAgent(
    name="executor",
    sub_agent=_executor_step,
    max_iterations=guardrails.max_executor_steps,
)
