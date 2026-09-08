from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:1337/v1",
    api_key="no-key",
)

# One shot prompting, directly give instructions, and start with a user request
SYSTEM_PROMPT = "You are a helpful Math assistant. You will help with math problems only. If asked any other problem, you will refuse to answer."
CONTENT = "Hey, I am Ayushya, tell me a joke."

res = client.chat.completions.create(
    model="gemma-4-12B-it-MLX-6bit",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": CONTENT},
    ],
)

print(res.choices[0].message.content)
