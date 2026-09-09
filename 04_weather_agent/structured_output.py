import json
import os
from typing import Optional

import requests
from dotenv import load_dotenv
from openai import OpenAI

# Using pydantic to define the output format, validating the model output.
from pydantic import BaseModel, Field

load_dotenv()

client = OpenAI(
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    api_key=os.getenv("GEMINI_API_KEY"),
)


class OutputFormat(BaseModel):
    step: str = Field(
        ...,
        description="The step of the output format, can be 'START', 'PLAN', 'OUTPUT', or 'TOOL_CALL'",
    )
    content: Optional[str] = Field(None, description="The content of the output step")
    tool: Optional[str] = Field(None, description="The tool to use for the output step")
    input: Optional[str] = Field(None, description="The input to the tool")


def get_weather(city: str):
    url = f"https://wttr.in/{city.lower()}?format=%C+%t"
    response = requests.get(url)

    if response.status_code == 200:
        return f"Current weather in {city}: {response.text}"
    else:
        return f"Error: Could not retrieve weather for {city}"


avail_tools = {
    "get_weather": get_weather,
}

SYSTEM_PROMPT = """
You are an expert AI assistant in resolving user queries, using chain of thought.
You work on START, PLAN and OUTPUT steps.
You need to first PLAN what needs to be done (can be multiple steps).
Once the planning and tool execution are complete, finally provide an OUTPUT.

Rules:
    - Strictly follow the given JSON output format.
    - Output only one step at a time.
    - If you need external information, emit a step with "TOOL_CALL".
    - Wait for the tool result before proceeding.

Output JSON format:
    {"step": "START" | "PLAN" | "TOOL_CALL" | "OUTPUT", "content": "string", "tool": "tool_name", "input": "tool_input"}

Available tools:
    - get_weather(city: str): returns the current weather in the given city.
"""

message_history = [
    {"role": "system", "content": SYSTEM_PROMPT},
]

while True:
    user_query = input("👉🏼 ")
    if not user_query.strip():
        continue

    message_history.append({"role": "user", "content": user_query})

    while True:
        res = client.chat.completions.parse(
            model="gemini-3.5-flash-lite",  # Update to a valid Gemini model if needed
            response_format=OutputFormat,
            messages=message_history,
        )

        raw_res = res.choices[0].message.content
        # Append the raw JSON string directly (do NOT json.dumps again)
        message_history.append({"role": "assistant", "content": raw_res})
        parsed_res = res.choices[0].message.parsed

        if parsed_res.step == "START":
            print(f"🌋 {parsed_res.content}")
            message_history.append({"role": "user", "content": "continue"})
            continue

        if parsed_res.step == "PLAN":
            print(f"🧠 {parsed_res.content}")
            # Nudge the assistant to continue so the next request doesn't end with an assistant turn
            message_history.append({"role": "user", "content": "continue"})
            continue

        if parsed_res.step == "TOOL_CALL":
            tool = parsed_res.tool
            tool_input = parsed_res.input
            print(f"🔧 TOOL_CALL {tool}: {tool_input}")

            tool_func = avail_tools.get(tool)
            if tool_func:
                tool_res = tool_func(tool_input)
            else:
                tool_res = f"Error: Tool '{tool}' not found."

            print(f"🔧 TOOL_RETURN {tool}: {tool_res}")

            # Send tool response as a user role turn
            tool_payload = {
                "step": "TOOL_RETURN",
                "tool": tool,
                "input": tool_input,
                "content": tool_res,
            }
            message_history.append(
                {"role": "user", "content": json.dumps(tool_payload)}
            )
            continue

        if parsed_res.step == "OUTPUT":
            print(f"🤖 {parsed_res.content}")
            break

    print("\n" + "=" * 40 + "\n")
