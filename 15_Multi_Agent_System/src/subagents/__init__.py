from .email_agent import email_agent, call_email_agent
from .cal_agent import cal_agent, call_cal_agent
from langchain_openai import ChatOpenAI
import os
from langchain.agents import create_agent
import dotenv

dotenv.load_dotenv()


__all__ = ["email_agent", "call_email_agent", "cal_agent", "call_cal_agent"]

SUPERVISOR_PROMPT = (
    "You are a helpful personal assistant. "
    "You can schedule calendar events and send emails. "
    "Break down user requests into appropriate tool calls and coordinate the results. "
    "When a request involves multiple actions, use multiple tools in sequence or in parallel as appropriate."
)

model = ChatOpenAI(
    model="deepseek/deepseek-v4-flash",
    api_key=os.environ.get("CMD_API_KEY"),
    base_url=os.environ.get("CMD_BASE_URL")
)

supervisor_agent = create_agent(
    model,
    tools=[call_cal_agent, call_email_agent],
    system_prompt=SUPERVISOR_PROMPT,
)

def main():
    print("\n\nMAS Supervisor")
    query = "Schedule a team standup for tomorrow at 9am"
    
    stream = supervisor_agent.stream_events(
        {"messages": [{"role": "user", "content": query}]},
        version="v3",
    )
    for kind, item in stream.interleave("messages", "tool_calls"):
        if kind == "messages":
            for token in item.text:
                print(token, end="", flush=True)
        elif kind == "tool_calls":
            print(f"\nTool call: {item.tool_name}({item.input})")
            print(f"Tool result: {item.output}")
