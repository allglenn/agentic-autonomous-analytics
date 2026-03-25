from dotenv import load_dotenv
load_dotenv()

import asyncio
from google.adk.runners import Runner
from google.genai.types import Content, Part
from orchestrator.pipeline import pipeline
from config.session import session_service


async def run_cli():
    runner = Runner(
        agent=pipeline,
        app_name="data_analyst",
        session_service=session_service,
    )
    session = await session_service.create_session(
        app_name="data_analyst",
        user_id="user",
        session_id="cli",
    )

    print("AI Data Analyst — powered by Google ADK + BigQuery")
    print("Type your question or 'exit' to quit.\n")

    while True:
        question = input("> ").strip()
        if question.lower() in ("exit", "quit"):
            break
        if not question:
            continue

        message = Content(role="user", parts=[Part(text=question)])
        events = runner.run(
            user_id="user",
            session_id=session.id,
            new_message=message,
        )
        for event in events:
            if event.is_final_response() and event.content:
                print("\n" + event.content.parts[0].text + "\n")


if __name__ == "__main__":
    asyncio.run(run_cli())
