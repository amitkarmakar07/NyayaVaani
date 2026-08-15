import os
from dotenv import load_dotenv

load_dotenv(override=True)

class Config:
    
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini/gemini-3.5-flash")
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 2048

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    WHISPER_MODEL: str = "whisper-1"

    SERPAPI_KEY: str = os.getenv("SERPAPI_KEY", "")


    CHROMA_DIR: str = "db/chromadb"
    ACT_DOCS_DIR: str = "data/act"
    EMBEDDING_MODEL: str = "BAAI/bge-base-en-v1.5"  
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150
    TOP_K_RETRIEVAL: int = 6
    RERANK_TOP_K: int = 3
    CROSS_ENCODER_MODEL: str = "BAAI/bge-reranker-base"
    RERANK_THRESHOLD: float = 0.0

    DEPARTMENTS_JSON: str = "data/departments.json"

    SQLITE_DB: str = "db/nyayavaani.db"

    LANGCHAIN_TRACING: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"

config = Config()