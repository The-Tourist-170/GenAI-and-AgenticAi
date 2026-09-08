from openai import OpenAI
import requests

client = OpenAI(
    api_key="no-key",
    base_url="http://127.0.0.1:1337/v1"
)


def get_weather(city: str):
    url = f"https://wttr.in/{city.lower()}?format=%C+%t"
    response = requests.get(url)

    if response.status_code == 200:
        return f"Current weather in {city}: {response.text}"
    else:
        return f"Error: Something went wrong"

def main():
    user_query = input("User >>> ")    
    response = client.chat.completions.create(
        model="gemma-4-12B-it-MLX-6bit",
        messages=[{"role": "user", "content": user_query}]
    )
    print(f"Sasha >>>: {response.choices[0].message.content}")
    

if __name__ == "__main__":
    main()
