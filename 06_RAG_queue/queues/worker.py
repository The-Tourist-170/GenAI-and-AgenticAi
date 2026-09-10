from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_qdrant import QdrantVectorStore
from pathlib import Path
from langchain_huggingface import HuggingFaceEmbeddings
from openai import OpenAI

model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={"device": "mps"},
    encode_kwargs={"normalize_embeddings": True}
)

#https://generativelanguage.googleapis.com/v1beta/openai/
client = OpenAI(
    base_url="http://127.0.0.1:1337/v1",
    api_key="GEMINI_API_KEY",
)

pdf_path = Path(__file__).parent / "nodejs.pdf"
loader = PyPDFLoader(pdf_path)
docs = loader.load()

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
)
chunks = text_splitter.split_documents(docs)

vector_db = QdrantVectorStore.from_documents(
    embedding=model,
    url="http://localhost:6333",
    collection_name="learning_rag",
    documents=chunks,
    check_compatibility=False,
)

def process_query(query: str):
    print(f"Processing query: {query}")

    res = vector_db.similarity_search(query)

    print(f"Results: {len(res)}")

    context = "\n\n\n".join([f"Page Content: {doc.page_content}\nPage Number: {doc.metadata['page']}\nFile Location: {doc.metadata['source']}" for doc in res])

    print(f"Context: {context}")

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
            {"role": "user", "content": query},
        ],
    )
    print(f"🤖: {resp.choices[0].message.content}")
    return resp.choices[0].message.content
