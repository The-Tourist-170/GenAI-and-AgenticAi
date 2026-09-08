from openai import OpenAI
import json
import requests

client = OpenAI(
    base_url="http://127.0.0.1:1337/v1",
    api_key="no-key",
)

def get_weather(city: str):
    url = f"https://wttr.in/{city.lower()}?format=%C+%t"
    response = requests.get(url)

    if response.status_code == 200:
        return f"Current weather in {city}: {response.text}"
    else:
        return f"Error: Something went wrong"

avail_tools = {
    "get_weather": get_weather,
}

# Chain of Thought: a prompt engineering technique that instructs an AI model to break down a complex problem into intermediate reasoning steps before arriving at a final answer.
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
"""

print("\n\n\n")

message_history = [
    {"role": "system", "content": SYSTEM_PROMPT},
]

while True:
    user_query = input("👉🏼 ")
    message_history.append({"role": "user", "content": user_query})
    
    while True:
        res = client.chat.completions.create(
            model="gemma-4-12B-it-MLX-6bit",
            response_format={"type": "json_object"},
            messages=message_history
        )
    
        raw_res = res.choices[0].message.content
        message_history.append({"role": "assistant", "content": raw_res})
        parsed_res = json.loads(raw_res)
    
        if parsed_res["step"] == "START":
            print("🌋 ", parsed_res["content"])
            continue
    
        if parsed_res["step"] == "PLAN":
            print(f"🧠 {parsed_res['content']}")
            continue
    
        if parsed_res["step"] == "TOOL_CALL":
            tool = parsed_res['tool']
            tool_input = parsed_res['input']
            print(f"🔧 TOOL_CALL {tool}: {tool_input}")
    
            tool_func = avail_tools[tool]
            tool_res = tool_func(tool_input)
            print(f"🔧 TOOL_RETURN {tool}: {tool_res}")
            message_history.append({"role": "developer", "content": json.dumps({
                "step": "TOOL_RETURN",
                "tool": tool,
                "input": tool_input,
                "content": tool_res
            })})
            continue
    
        if parsed_res["step"] == "OUTPUT":
            print(f"🤖 {parsed_res['content']}")
            break
        
    print("\n\n\n")
