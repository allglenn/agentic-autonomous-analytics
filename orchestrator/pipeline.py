from google.adk.agents import SequentialAgent, LoopAgent
from agents.planner import planner_agent
from agents.executor import executor_agent
from agents.critic import critic_gate

# Outer loop: Executor runs its ReAct loop → Critic validates.
# CriticGate escalates when validated=True, breaking the loop.
# If validated=False, critic_notes lands in session state and
# the Executor retries with that feedback.
analysis_loop = LoopAgent(
    name="analysis_loop",
    sub_agents=[executor_agent, critic_gate],
    max_iterations=3,
)

# Full pipeline:
#   Planner → analysis_loop (Executor ↔ Critic until validated or max retries)
pipeline = SequentialAgent(
    name="data_analyst_pipeline",
    sub_agents=[planner_agent, analysis_loop],
)
