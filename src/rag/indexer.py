"""
RAG Indexer — Industry-grade PDF indexing pipeline
Uses semantic chunking + BGE embeddings + ChromaDB
Run once: python -m src.rag.indexer
"""

import os
import json
from pathlib import Path
from loguru import logger
from typing import List, Dict

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document

from config import config


def load_pdfs(docs_dir: str) -> List[Document]:
    """Load all PDFs with rich metadata tagging."""
    all_docs = []
    pdf_dir = Path(docs_dir)

    if not pdf_dir.exists():
        logger.error(f"PDF directory not found: {docs_dir}")
        return []

    pdf_files = list(pdf_dir.glob("*.pdf"))
    logger.info(f"Found {len(pdf_files)} PDFs to index")

    for pdf_path in pdf_files:
        try:
            logger.info(f"Loading: {pdf_path.name}")
            loader = PyPDFLoader(str(pdf_path))
            pages = loader.load()

            # Tag each page with rich metadata
            act_name = pdf_path.stem  # filename without extension
            department_tags = _get_department_tags(act_name)

            for page in pages:
                page.metadata.update({
                    "source": pdf_path.name,
                    "act_name": act_name,
                    "page_number": page.metadata.get("page", 0) + 1,
                    "departments": json.dumps(department_tags),
                    "doc_type": "legal_act"
                })

            all_docs.extend(pages)
            logger.success(f"Loaded {len(pages)} pages from {pdf_path.name}")

        except Exception as e:
            logger.error(f"Failed to load {pdf_path.name}: {e}")

    logger.info(f"Total pages loaded: {len(all_docs)}")
    return all_docs


def _get_department_tags(act_name: str) -> List[str]:
    """Map act names to department categories for filtered retrieval."""
    mapping = {
        "RTI Act 2005": ["road", "water_supply", "property_tax", "general"],
        "Consumer Protection Act 2019": ["consumer_fraud", "hospital_health", "banking", "general"],
        "Consumer Forum Filing Guide": ["consumer_fraud", "general"],
        "CrPC 1973": ["police"],
        "IPC 1860": ["police", "corruption_cvc"],
        "Electricity Act 2003": ["electricity"],
        "Environment Protection Act 1986": ["pollution_general", "pollution_air"],
        "Land Acquisition Act 2013": ["land_dispute"],
        "Lokpal Act 2013": ["corruption_lokpal", "corruption_cvc"],
        "NFSA 2013": ["ration_pds"],
        "Prevention of Corruption Act 1988": ["corruption_cvc", "corruption_lokpal"],
        "RTE Act 2009": ["education_school", "education_higher"],
        "Banking Regulation Act 1949": ["banking"],
    }

    for key, tags in mapping.items():
        if key.lower() in act_name.lower() or act_name.lower() in key.lower():
            return tags

    return ["general"]


def chunk_documents(docs: List[Document]) -> List[Document]:
    """
    Semantic-aware chunking using RecursiveCharacterTextSplitter.
    Splits on paragraph boundaries first, then sentences.
    Preserves legal section structure.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        separators=[
            "\n\n\n",    # section breaks
            "\n\n",      # paragraph breaks
            "\n",        # line breaks
            ". ",        # sentence breaks
            ", ",
            " ",
            ""
        ],
        length_function=len,
        is_separator_regex=False
    )

    chunks = splitter.split_documents(docs)

    # Filter out very short/noisy chunks
    chunks = [c for c in chunks if len(c.page_content.strip()) > 100]

    logger.info(f"Created {len(chunks)} chunks from {len(docs)} pages")
    return chunks


def build_vector_store(chunks: List[Document]) -> Chroma:
    """Build ChromaDB vector store with BGE embeddings."""

    logger.info(f"Loading embedding model: {config.EMBEDDING_MODEL}")

    embeddings = HuggingFaceEmbeddings(
        model_name=config.EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={
            "normalize_embeddings": True,  # important for BGE models
            "batch_size": 32
        }
    )

    # Create output directory
    os.makedirs(config.CHROMA_DIR, exist_ok=True)

    logger.info("Building ChromaDB vector store...")

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=config.CHROMA_DIR,
        collection_name="nyayavaani_acts",
        collection_metadata={"hnsw:space": "cosine"}  # cosine similarity
    )

    vectorstore.persist()
    logger.success(f"Vector store built with {len(chunks)} chunks")
    logger.success(f"Saved to: {config.CHROMA_DIR}")

    return vectorstore


def run_indexing():
    """Full indexing pipeline."""
    logger.info("=" * 60)
    logger.info("NyayaVaani RAG Indexing Pipeline Started")
    logger.info("=" * 60)

    # Step 1: Load PDFs
    docs = load_pdfs(config.ACT_DOCS_DIR)
    if not docs:
        logger.error("No documents loaded. Check your PDF directory.")
        return

    # Step 2: Chunk
    chunks = chunk_documents(docs)

    # Step 3: Build vector store
    vectorstore = build_vector_store(chunks)

    # Step 4: Verify
    test_query = "What are citizen rights when filing a complaint?"
    results = vectorstore.similarity_search(test_query, k=3)
    logger.info(f"\nVerification test — query: '{test_query}'")
    for i, r in enumerate(results):
        logger.info(f"  Result {i+1}: {r.metadata.get('act_name')} | Page {r.metadata.get('page_number')}")

    logger.success("\n✅ Indexing complete! RAG pipeline ready.")


if __name__ == "__main__":
    run_indexing()