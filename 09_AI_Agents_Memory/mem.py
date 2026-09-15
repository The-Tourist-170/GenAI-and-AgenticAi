from mem0 import Memory
from openai import OpenAI
import json

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
            "collection_name": "mem0_minilm",
            "embedding_model_dims": 384, 
        },
    },
}

mem_client = Memory.from_config(config)

client = OpenAI(
    base_url="http://127.0.0.1:1337/v1", 
    api_key="not-needed"
)
while True:
    
    user_query = input(">>> ")

    search_mem = mem_client.search(query=user_query, filters={"user_id": "ken"})

    memories = [
        f"ID: {mem.get('id')}\nMemory: {mem.get('memory')}" for mem in search_mem.get('results')
    ]

    print("Mem found: >>> ", json.dumps(search_mem))
    
    SYSTEM_PROMPT = f"""
        Here is the context about the user:
            {json.dumps(search_mem)}
    """
    
    res = client.chat.completions.create(
        model="gemma-4-12B-it-MLX-6bit",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_query}
        ]
    )
    
    ai_res = res.choices[0].message.content
    print(ai_res)   
    
    mem_client.add(
        messages=[
            {"role": "user", "content": user_query},
            {"role": "assistant", "content": ai_res},
        ],
        user_id="ken"
    )
    print(">>> Memory Synced\n")
