from gc import collect

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={"device": "mps"},
    encode_kwargs={"normalize_embeddings": True}
)

#https://generativelanguage.googleapis.com/v1beta/openai/
client = OpenAI(
    base_url="http://127.0.0.1:1337/v1",
    api_key=os.getenv("GEMINI_API_KEY"),
)

vector_db = QdrantVectorStore.from_existing_collection(
    embedding=model,
    url="http://localhost:6333",
    collection_name="learning_rag",
)

while True:
    user_query = input("🤖 Hey, How can I help you with today?\n")
    
    res = vector_db.similarity_search(user_query)
    print(f"Found {len(res)} results")
    context = "\n\n\n".join([f"Page Content: {doc.page_content}\nPage Number: {doc.metadata['page']}\nFile Location: {doc.metadata['source']}" for doc in res])
    
    SYSTEM_PROMPT = f"""
    You are a helpful assistant. You answer question based on the available context,
    retrieved from a pdf file along with page_contents and page number.
    You should only answer questions that are related to the context, and based on the context and navigate the user to the relevant page for him to know more.
    
    Context:
    {context}
    """
    
    resp = client.chat.completions.create(
        model="gemma-4-12B-it-MLX-6bit",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_query},
        ],
    )
    
    print(f"🤖: {resp.choices[0].message.content}")
