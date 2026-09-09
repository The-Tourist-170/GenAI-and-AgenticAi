import json
import os
from typing import Optional

import requests
from dotenv import load_dotenv
from openai import OpenAI
import subprocess

# Using pydantic to define the output format, validating the model output.
from pydantic import BaseModel, Field

load_dotenv()

#https://generativelanguage.googleapis.com/v1beta/openai/
client = OpenAI(
    base_url="http://127.0.0.1:1337/v1",
    api_key=os.getenv("GEMINI_API_KEY"),
)

def run_cmd(cmd: str):
    try:
        result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
        if result.returncode == 0:
            return result.stdout.strip() if result.stdout else "Success (no output)"
        else:
            return f"Error: {result.stderr.strip()}"
    except Exception as e:
        return f"Execution failed: {str(e)}"


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
    "run_cmd": run_cmd,
}

# Chain of Thought
SYSTEM_PROMPT = """
You are an expert AI assistant in resolving user queries, using chain of thought.
You work on START, PLAN and OUTPUT steps.
You need to first PLAN, what needs to return the PLAN can be multiple steps,
Once you think now PLAN has been done, finally, you can give an OUTPUT.

Rules:
    - Should strictly follow the given JSON output format.
    - Only run one step at a time.
    - The sequence of steps is START (where user is an input), then PLAN (that can be multiple times), then OUTPUT (which is going to be displayed to the user).
    - You can also call a suitable TOOL if required from a list of available tools.
    - After calling a TOOL, you must wait for the result which is the response from the TOOL before moving to the next step.

Output JSON format:
    {"step": "START" | "PLAN" | "OUTPUT" | "TOOL", "content": "string"}

Available tools:
    - get_weather(city: str): returns the current weather in the given city.
    - run_cmd(cmd: str): Takes a Linux system command as string and executes the command on user's system and returns the output from that command.

Example 1:
    START: hey, can you solve 2+3*5/10 ?
    PLAN: {"step": "PLAN", "content": "seems like the user is interested in maths problem"}
    PLAN: {"step": "PLAN", "content": "the user is asking for the result of the maths problem"}
    PLAN: {"step": "OUTPUT", "content": "looking at the problem, we should solve this by using the BODMAS method."}
    PLAN: {"step": "OUTPUT", "content": "Yes, the BODMAS approach is correct here to be used to solve this problem."}
    PLAN: {"step": "OUTPUT", "content": "first, we must divide 5 by 10."}
    PLAN: {"step": "OUTPUT", "content": "then, we must multiply the result by 2."}
    PLAN: {"step": "OUTPUT", "content": "finally, we must add 3 to the result."}
    PLAN: {"step": "OUTPUT", "content": "Great, we have finally solved the problem, and have our answer that is 3.5."}
    OUTPUT: {"step": "OUTPUT", "content": "3.5"}

Example 2:
    START: Hey, what is the weather of Jhansi?
    PLAN: {"step": "PLAN", "content": "seems like the user is interested in weather"}
    PLAN: {"step": "PLAN", "content": "the user is asking for the weather of Jhansi"}
    PLAN: {"step": "PLAN", "content": "looking at the problem, I can't directly fetch weather of a city as an LLM."}
    PLAN: {"step": "PLAN", "content": "Let's check if there is any available tool to fetch weather data."}
    PLAN: {"step": "PLAN", "content": "Yes, we do have a tool named get_weather."}
    PLAN: {"step": "PLAN", "content": "I need to call this tool using jhansi as input parameter."}
    PLAN: {"step": "TOOL_CALL", "tool": "get_weather", "input": "jhansi"}
    PLAN: {"step": "TOOL_RETURN", "tool": "get_weather", "input": "jhansi", "content": "The temperature of Jhansi is cool with 23 C"}
    PLAN: {"step": "PLAN", "content": "Great, I have the weather data of Jhansi."}
    OUTPUT: {"step": "OUTPUT", "content": "The current temperature of Jhansi is 23 C."}

Example 3:
    START: Hey, what files are in my current directory?
    PLAN: {"step": "PLAN", "content": "The user wants to know the contents of their current working directory."}
    PLAN: {"step": "PLAN", "content": "I can use the run_cmd tool to execute a Linux command to list files."}
    PLAN: {"step": "PLAN", "content": "The command 'ls -1' will list the files clearly."}
    PLAN: {"step": "TOOL_CALL", "tool": "run_cmd", "input": "ls -1"}
    PLAN: {"step": "TOOL_RETURN", "tool": "run_cmd", "input": "ls -1", "content": "main.py\nrequirements.txt\nREADME.md"}
    PLAN: {"step": "PLAN", "content": "I have successfully retrieved the list of files."}
    OUTPUT: {"step": "OUTPUT", "content": "In your current directory, you have the following files: main.py, requirements.txt, and README.md."}

Example 4:
    START: Can you check what version of Python is installed on my machine?
    PLAN: {"step": "PLAN", "content": "The user wants to know the installed Python version on their system."}
    PLAN: {"step": "PLAN", "content": "I can check this by running a terminal command using the run_cmd tool."}
    PLAN: {"step": "PLAN", "content": "The command 'python3 --version' will output the required information."}
    PLAN: {"step": "TOOL_CALL", "tool": "run_cmd", "input": "python3 --version"}
    PLAN: {"step": "TOOL_RETURN", "tool": "run_cmd", "input": "python3 --version", "content": "Python 3.10.12"}
    PLAN: {"step": "PLAN", "content": "I received the python version from the system output."}
    OUTPUT: {"step": "OUTPUT", "content": "You currently have Python 3.10.12 installed on your machine."}

Example 5:
    START: Can you create a new folder called "test_dir" and create an empty file named "notes.txt" inside it?
    PLAN: {"step": "PLAN", "content": "The user wants to create a directory and a file within that directory."}
    PLAN: {"step": "PLAN", "content": "I can use the run_cmd tool to execute terminal commands for this."}
    PLAN: {"step": "PLAN", "content": "I will use 'mkdir test_dir' to create the folder and 'touch test_dir/notes.txt' to create the file. I can chain them with &&."}
    PLAN: {"step": "TOOL_CALL", "tool": "run_cmd", "input": "mkdir test_dir && touch test_dir/notes.txt"}
    PLAN: {"step": "TOOL_RETURN", "tool": "run_cmd", "input": "mkdir test_dir && touch test_dir/notes.txt", "content": "0"}
    PLAN: {"step": "PLAN", "content": "The command executed successfully since the system returned 0."}
    OUTPUT: {"step": "OUTPUT", "content": "I have successfully created the 'test_dir' folder and added the 'notes.txt' file inside it for you."}
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
            model="gemma-4-12B-it-MLX-6bit",
            response_format=OutputFormat,
            messages=message_history,
        )

        raw_res = res.choices[0].message.content
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
