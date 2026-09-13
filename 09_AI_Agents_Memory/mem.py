from mem0 import Memory
from openai import OpenAI

config = {
    "version": "v1.1",
    "embedder": {
        "provider": "huggingface",
        "config": {
            "model": "sentence-transformers/all-MiniLM-L6-v2",
        },
    },
    "llm": {
        "provider": "openai",
        "config": {
            "model": "gemma-4-12B-it-MLX-6bit",
            "openai_base_url": "http://127.0.0.1:1337/v1",  
            "api_key": "not-needed",  
        },
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "host": "localhost",
            "port": 6333,
        },
    },
}

mem_client = Memory.from_config(config)

client = OpenAI(
    base_url="http://127.0.0.1:1337/v1", 
    api_key="not-needed"
)

user_query = input(">>>")

res = client.chat.completions.create(
    model="gemma-4-12B-it-MLX-6bit",
    messages=[{"role": "user", "content": user_query}]
)

ai_res = res.choices[0].message.content
print(ai_res)   

mem_client.add(
    messages=[
        {"role": "user", "content": user_query},
        {"role": "assistant", "content": ai_res},
    ]
)
print(">>> Memory Synced")
