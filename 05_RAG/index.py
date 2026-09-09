from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from pathlib import Path

pdf_path = Path(__file__).parent / "nodejs.pdf"
loader = PyPDFLoader(pdf_path)
docs = loader.load()

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
)
chunks = text_splitter.split_documents(docs)

#Vector Embeddings
model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={"device": "mps"},
    encode_kwargs={"normalize_embeddings": True}
)

vector_store = QdrantVectorStore.from_documents(
    documents=chunks,
    embedding=model,
    url="http://localhost:6333",
    prefer_grpc=False,
    collection_name="learning_rag"
)
print(f"Successfully embedded and stored {len(chunks)} chunks in Qdrant!")
