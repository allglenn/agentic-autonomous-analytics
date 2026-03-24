from google.adk.agents import LlmAgent
from config.settings import settings
from models.answer import FinalAnswer

CRITIC_INSTRUCTION = """
You are a data analysis critic. Your job is to validate the draft answer produced by the executor.

Check for:
1. Correctness — are the conclusions supported by the data?
2. Completeness — is the success criteria fully addressed?
3. Clarity — is the answer understandable to a business user?

If the answer is valid, output a FinalAnswer with validated=true.
If not, output a FinalAnswer with validated=false and clear critic_notes
explaining what is missing or wrong so the executor can retry.
"""

critic_agent = LlmAgent(
    name="critic",
    model=settings.model_name,
    instruction=CRITIC_INSTRUCTION,
    output_schema=FinalAnswer,
    output_key="final_answer",
)
