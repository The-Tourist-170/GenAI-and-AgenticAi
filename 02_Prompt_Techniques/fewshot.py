from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:1337/v1",
    api_key="no-key",
)

# Few shot prompting, provide examples before the user request to refine the model's responses
SYSTEM_PROMPT = """
You are a helpful Math assistant. You will help with math problems only. If asked any other problem, you will refuse to answer.

Examples:
    Q. What is the square root of 16?
    A. The square root of 16 is 4.

    Q. What is (a+b)^2?
    A. (a+b)^2 is the square of the sum of a and b and can be calculated as a^2 + b^2 + 2ab.

    Q. Suggest me a science/maths movies.
    A. I am sorry, but I can only help with math problems. If you have a math question, please feel free to ask!

    Q. Tell me a Math joke.
    A. I am sorry, but I can only help with math problems. If you have a math question, please feel free to ask!
"""

CONTENT = "Hey, I am Ayushya, what is an adjective?"

res = client.chat.completions.create(
    model="gemma-4-12B-it-MLX-6bit",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": CONTENT},
    ],
)

print(res.choices[0].message.content)
