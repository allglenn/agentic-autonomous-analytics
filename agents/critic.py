from typing import AsyncGenerator
from google.adk.agents import LlmAgent, BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from config.settings import settings
from models.answer import FinalAnswer

CRITIC_INSTRUCTION = """
You are a data analysis critic. Your job is to validate the draft answer produced by the executor.

Check for:
1. Correctness — are the conclusions supported by the data?
2. Completeness — is the success criteria from the analysis_plan fully addressed?
3. Clarity — is the answer understandable to a business user?

If the answer is valid, output a FinalAnswer with validated=true.
If not, output a FinalAnswer with validated=false and clear critic_notes
explaining what is missing or wrong so the executor can retry.

IMPORTANT — summary writing style:
- Write the summary as a direct, conversational answer to the user's question.
- Start with the key number or insight, not with a description of what was queried.
- Use natural language, as if speaking to a colleague.
- Bad:  "The query for the metric 'units_sold' over 'last_month' returned 1,930."
- Good: "Last month, 1,930 products were sold across all channels."
- Bad:  "A total of 1,930 products were sold last month."  (too formal)
- Good: "You sold 1,930 products last month."
- Keep it to 1–2 sentences maximum.
"""

_critic_llm = LlmAgent(
    name="critic_llm",
    model=settings.model_critic,
    instruction=CRITIC_INSTRUCTION,
    output_schema=FinalAnswer,
    output_key="final_answer",
)


class CriticGate(BaseAgent):
    """
    Wraps the critic LlmAgent.
    Reads validated from session state after the critic runs.
    Escalates the outer LoopAgent when the answer is validated — stopping retries.
    Lets the loop continue when validated=False so the executor retries.
    """

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        # Run the critic LlmAgent
        async for event in self.sub_agents[0].run_async(ctx):
            yield event

        # ADK stores output_schema result as a dict in session state
        final_answer: dict = ctx.session.state.get("final_answer", {})
        validated = final_answer.get("validated", False)

        if validated:
            # Escalate → LoopAgent breaks out, analysis is done
            yield Event(
                author=self.name,
                actions=EventActions(escalate=True),
            )
        # If not validated, critic_notes is in state — executor will
        # see it on the next iteration via conversation history


critic_gate = CriticGate(
    name="critic",
    sub_agents=[_critic_llm],
)
