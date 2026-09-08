from openai import OpenAI
import json

client = OpenAI(
    base_url="http://127.0.0.1:1337/v1",
    api_key="no-key",
)

# Chain of Thought: a prompt engineering technique that instructs an AI model to break down a complex problem into intermediate reasoning steps before arriving at a final answer.
SYSTEM_PROMPT = """
You are an expert AI assistant in resolving user queries, using chain of thought.
You work on START, PLAN and OUTPUT steps.
You need to first PLAN, what needs to return the PLAN can be multiple steps,
Once you think now PLAN has been done, finally, you can give an OUTPUT.

Rules:
    - should strictly follow the given JSON output format.
    - only run one step at a time.
    - The sequence of steps is START (where user is an input), then PLAN (that can be multiple times), then OUTPUT (which is going to be displayed to the user).

Output JSON format:
    {"step": "START" | "PLAN" | "OUTPUT", "content": "string"}

Examples:
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
    
"""

print("\n\n\n")

message_history = [
    {"role": "system", "content": SYSTEM_PROMPT},
]

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

    if parsed_res["step"] == "OUTPUT":
        print(f"🤖 {parsed_res['content']}")
        break
    
print("\n\n\n")
