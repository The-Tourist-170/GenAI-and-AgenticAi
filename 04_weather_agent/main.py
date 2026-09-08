from openai import OpenAI

client = OpenAI(
    api_key="no-key",
    base_url="http://127.0.0.1:1337/v1"
)

def main():
    user_query = input("User >>> ")    
    response = client.chat.completions.create(
        model="gemma-4-12B-it-MLX-6bit",
        messages=[{"role": "user", "content": user_query}]
    )
    print(f"Sasha >>>: {response.choices[0].message.content}")

if __name__ == "__main__":
    main()
