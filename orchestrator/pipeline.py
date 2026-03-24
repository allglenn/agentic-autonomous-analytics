from google.adk.agents import SequentialAgent
from agents import planner_agent, executor_agent, critic_agent

# Full analysis pipeline:
#   Planner → Executor (ReAct loop) → Critic
#
# Each agent reads from and writes to shared session state via output_key.
# The Critic can send feedback that routes back to the Executor if needed.

pipeline = SequentialAgent(
    name="data_analyst_pipeline",
    sub_agents=[
        planner_agent,
        executor_agent,
        critic_agent,
    ],
)
