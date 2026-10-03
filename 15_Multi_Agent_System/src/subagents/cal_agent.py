import os
from datetime import date
from typing import Optional

import dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

dotenv.load_dotenv()

client = ChatOpenAI(
    model="deepseek/deepseek-v4-flash",
    api_key=os.getenv("CMD_API_KEY"),
    base_url=os.getenv("CMD_BASE_URL"),
    temperature=0.0,
)


@tool
def create_calendar_event(
    title: str,
    start_time: str,
    end_time: str,
    attendees: list[str] = [],
    location: str = "",
) -> str:
    """Create a calendar event. Requires exact ISO datetime format."""
    return f"Event created: '{title}' from {start_time} to {end_time} with {len(attendees)} attendees"


@tool
def get_available_time_slots(
    date: str,  # ISO format: "YYYY-MM-DD"
    duration_minutes: int,
    attendees: list[str] = [],
) -> list[str]:
    """Check calendar availability for given attendees on a specific date."""
    return ["09:00", "14:00", "16:00"]


CALENDAR_AGENT_PROMPT = (
    f"Today's date is {date.today().isoformat()}. "
    "You are a calendar scheduling assistant. "
    "Parse natural language scheduling requests (e.g., 'next Tuesday at 2pm') "
    "into proper ISO datetime formats. "
    "Use get_available_time_slots to check availability when needed. "
    "If there is no suitable time slot, stop and confirm unavailability in your response. "
    "Use create_calendar_event to schedule events. "
    "Always confirm what was scheduled in your final response."
)

cal_agent = create_react_agent(
    model=client,
    tools=[create_calendar_event, get_available_time_slots],
    prompt=CALENDAR_AGENT_PROMPT,
)


@tool
def call_cal_agent(request: str) -> str:
    """Delegate calendar scheduling, availability lookups, and event creation to the calendar specialist agent.

    Use this tool when the user wants to schedule a meeting, check time slot availability,
    or book an appointment using natural language dates or times (e.g., 'next Tuesday at 2pm',
    'tomorrow morning', 'check availability for Friday').

    Args:
        request: The natural language scheduling or availability instruction to process.

    Returns:
        A confirmation string stating the scheduled event details, or notification
        that no suitable time slot was available.
    """
    res = cal_agent.invoke({"messages": [{"role": "user", "content": request}]})
    final_message = res["messages"][-1]
    return getattr(final_message, "text", str(final_message.content))


def main():
    print("<<-----------CALENDAR AGENT TEST--------->>")
    query = "Schedule a team meeting next Tuesday at 2pm for 1 hour"
    result = call_cal_agent.invoke({"request": query})
    print("\nResult:\n", result)


if __name__ == "__main__":
    main()
