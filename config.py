import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # LLM (Gemini)
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    LLM_MODEL: str = "gemini-flash-lite-latest"
    LLM_TEMPERATURE: float = 0.1  # low for factual accuracy
    LLM_MAX_TOKENS: int = 2048

    # Voice
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    WHISPER_MODEL: str = "whisper-1"

    # Search
    SERPAPI_KEY: str = os.getenv("SERPAPI_KEY", "")

    # RAG
    CHROMA_DIR: str = "db/chromadb"
    ACT_DOCS_DIR: str = "data/act"
    EMBEDDING_MODEL: str = "BAAI/bge-base-en-v1.5"  # best free embedding model
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150
    TOP_K_RETRIEVAL: int = 6
    RERANK_TOP_K: int = 3

    # Data
    DEPARTMENTS_JSON: str = "data/departments.json"

    # DB
    SQLITE_DB: str = "db/nyayavaani.db"

    # LLMOps
    LANGCHAIN_TRACING: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"

config = Config()