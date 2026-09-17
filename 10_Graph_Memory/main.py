from mem0 import Memory
from openai import OpenAI
import json
import dotenv
import os

dotenv.load_dotenv()
# print(os.getenv("NEO_USERNAME"))
# print(os.getenv("NEO_PASSWORD"))
# print(os.getenv("NEO_URI"))
# print(os.getenv("CMD_API_KEY"))

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
            "model": "deepseek/deepseek-v4-flash",
            "openai_base_url": "http://127.0.0.1:1920",  
            "api_key": os.getenv("CMD_API_KEY"),  
        },
    },
    "graph_store": {
        "provider": "neo4j",
        "config": {
            "username": os.getenv("NEO_USERNAME"),
            "password": os.getenv("NEO_PASSWORD"),
            "url": os.getenv("NEO_URI"),
            "database": "60c9da61",
        },
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "host": "localhost",
            "port": 6333,
            "collection_name": "test",
            "embedding_model_dims": 384, 
        },
    },
}

mem_client = Memory.from_config(config)

client = OpenAI(
    base_url="http://127.0.0.1:1920", 
    api_key=os.getenv("CMD_API_KEY")
)

while True:
    
    user_query = input(">>> ")

    # for mem version >= 2.0.0
    # search_mem = mem_client.search(query=user_query, filters={"user_id": "alex"})

    # for mem version < 2.0.0
    search_mem = mem_client.search(query=user_query, user_id="alex")
    
    memories = [
        f"ID: {mem.get('id')}\nMemory: {mem.get('memory')}" for mem in search_mem.get('results')
    ]

    print("Mem found: >>> ", json.dumps(search_mem))
    
    SYSTEM_PROMPT = f"""
        Here is the context about the user:
            {json.dumps(search_mem)}
    """
    
    res = client.chat.completions.create(
        model="deepseek/deepseek-v4-flash",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_query}
        ]
    )
    
    ai_res = res.choices[0].message.content
    print(ai_res)   
    
    sync_result = mem_client.add(
        messages=[
            {"role": "user", "content": user_query},
            {"role": "assistant", "content": ai_res},
        ],
        user_id="alex"
    )
    print("Sync Result Details:", json.dumps(sync_result, indent=2))
    print("\n>>> Memory Synced\n")
