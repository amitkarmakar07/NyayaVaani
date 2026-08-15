from typing import List, Dict, Optional, Tuple
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from sentence_transformers import CrossEncoder

from langchain_core.prompts import ChatPromptTemplate

from config import config

from langfuse import observe
from langfuse.langchain import CallbackHandler


class HybridRetriever:
    """
    Hybrid Dense + Sparse retriever.
    Dense: BGE embeddings via ChromaDB (semantic similarity)
    Sparse: BM25 (keyword matching for legal terms/section numbers)
    """

    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(
            model_name=config.EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True}
        )
        self.vectorstore = Chroma(
            persist_directory=config.CHROMA_DIR,
            embedding_function=self.embeddings,
            collection_name="nyayavaani_acts"
        )
        self._bm25_index = None
        self._bm25_docs = None
        logger.info("HybridRetriever initialized")

    def _build_bm25_index(self, docs: List[Document]):
        """Build BM25 index from documents for sparse retrieval."""
        tokenized = [doc.page_content.lower().split() for doc in docs]
        self._bm25_index = BM25Okapi(tokenized)
        self._bm25_docs = docs

    def dense_search(
        self,
        query: str,
        k: int = config.TOP_K_RETRIEVAL,
        department_filter: Optional[str] = None
    ) -> List[Tuple[Document, float]]:
        """Semantic dense search via ChromaDB."""
        try:
            where_filter = None

            results = self.vectorstore.similarity_search_with_relevance_scores(
                query=query,
                k=k
            )
            return results
        except Exception as e:
            logger.error(f"Dense search failed: {e}")
            return []

    def sparse_search(self, query: str, k: int = config.TOP_K_RETRIEVAL) -> List[Document]:
        """BM25 keyword search — good for section numbers, act names."""
        if self._bm25_index is None:
            all_docs = self.vectorstore.get()
            if not all_docs or not all_docs.get("documents"):
                return []
            docs = [
                Document(
                    page_content=all_docs["documents"][i],
                    metadata=all_docs["metadatas"][i] if all_docs["metadatas"] else {}
                )
                for i in range(len(all_docs["documents"]))
            ]
            self._build_bm25_index(docs)

        tokenized_query = query.lower().split()
        scores = self._bm25_index.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [self._bm25_docs[i] for i in top_indices]

    @observe(as_type="span", name="hybrid_search")
    def hybrid_search(
        self,
        query: str,
        k: int = config.TOP_K_RETRIEVAL
    ) -> List[Tuple[Document, float]]:
        """
        Combines dense + sparse results with RRF (Reciprocal Rank Fusion).
        Industry standard for hybrid retrieval.
        """
        dense_results = self.dense_search(query, k=k)
        sparse_results = self.sparse_search(query, k=k)

        rrf_scores: Dict[str, float] = {}
        doc_map: Dict[str, Document] = {}
        rrf_k = 60 

        for rank, (doc, score) in enumerate(dense_results):
            doc_id = doc.page_content[:100]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (rrf_k + rank + 1)
            doc_map[doc_id] = doc

        for rank, doc in enumerate(sparse_results):
            doc_id = doc.page_content[:100]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (rrf_k + rank + 1)
            doc_map[doc_id] = doc

        # Sort by combined RRF score
        sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)[:k]
        return [(doc_map[doc_id], rrf_scores[doc_id]) for doc_id in sorted_ids]


class LegalRAGPipeline:
    """
    Hybrid Legal RAG pipeline (Dense + BM25 Sparse Search + Cross-Encoder Reranking).
    1. Retrieve candidates via Hybrid Search (Dense ChromaDB + BM25 Sparse)
    2. Grade relevance of each chunk with Cross-Encoder
    3. Filter out irrelevant chunks (prevents hallucination)
    4. Generate grounded answer
    """

    def __init__(self):
        self.retriever = HybridRetriever()
        self.llm = ChatGoogleGenerativeAI(
            model=config.LLM_MODEL,
            google_api_key=config.GOOGLE_API_KEY,
            temperature=0.0 
        )
        self.cross_encoder = CrossEncoder(config.CROSS_ENCODER_MODEL)
        logger.info(f"LegalRAGPipeline initialized with CrossEncoder: {config.CROSS_ENCODER_MODEL}")

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=6))
    @observe(as_type="span", name="retrieve_and_rerank")
    def retrieve_and_rerank(
        self,
        query: str,
        department: Optional[str] = None
    ) -> Dict:
        """
        Full Hybrid Legal RAG pipeline using CrossEncoder reranking.
        Returns graded relevant chunks + confidence.
        """
        logger.info(f"RAG query: {query[:80]}...")

        candidates = self.retriever.hybrid_search(query, k=config.TOP_K_RETRIEVAL)
        logger.info(f"Retrieved {len(candidates)} candidate chunks")

        if not candidates:
            return {
                "chunks": [],
                "confidence": "low",
                "total_retrieved": 0,
                "total_relevant": 0
            }

        # Cross-Encoder Reranking
        pairs = [[query, doc.page_content] for doc, _ in candidates]
        scores = self.cross_encoder.predict(pairs)

        relevant_chunks = []
        for i, (doc, _) in enumerate(candidates):
            score = float(scores[i])
            relevant_chunks.append({
                "content": doc.page_content,
                "source": doc.metadata.get("act_name", "Unknown Act"),
                "page": doc.metadata.get("page_number", "N/A"),
                "score": round(score, 3)
            })

        # Sort by cross-encoder score descending
        relevant_chunks = sorted(relevant_chunks, key=lambda x: x["score"], reverse=True)

        logger.info(f"Relevant chunks after reranking: {len(relevant_chunks)}/{len(candidates)}")

        if len(relevant_chunks) >= 2:
            confidence = "high"
        elif len(relevant_chunks) == 1:
            confidence = "medium"
        else:
            confidence = "low"

        return {
            "chunks": relevant_chunks[:config.RERANK_TOP_K],
            "confidence": confidence,
            "total_retrieved": len(candidates),
            "total_relevant": len(relevant_chunks)
        }

    # Alias for backward compatibility
    retrieve_and_grade = retrieve_and_rerank

    @observe(as_type="span", name="answer_question")
    def answer_question(self, question: str, department: Optional[str] = None) -> Dict:
        """
        Full RAG answer generation with anti-hallucination.
        """
        retrieval = self.retrieve_and_rerank(question, department)
        chunks = retrieval["chunks"]
        confidence = retrieval["confidence"]

        if confidence == "low":
            logger.info("Low confidence in retrieval - allowing LLM to determine response based on context")

        context = ""
        for i, chunk in enumerate(chunks):
            context += f"\n--- Source {i+1}: {chunk['source']} (Page {chunk['page']}) ---\n"
            context += chunk["content"] + "\n"

        answer_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are NyayaVaani's Legal Assistant — an expert in Indian government laws and citizen rights.

Your role: Answer citizen questions accurately using ONLY the provided legal documents.

STRICT RULES:
1. ONLY use information from the provided document excerpts
2. If information is not in the documents, say "This specific detail is not in my documents. Please verify at [relevant portal]."
3. Always cite the Act name and section when referencing law
4. Use simple, clear language a common Indian citizen can understand
5. Never guess or infer beyond what documents state
6. If partial info available, share it and note what's missing
7. EXCEPTION: If the user is just saying hello, offering a greeting, or asking a casual conversational question (e.g., "how are you?"), ignore all the rules above. DO NOT say "This specific detail is not in my documents". Just respond politely and naturally like a normal, friendly assistant.

Response format:
- Direct answer first
- Legal basis (Act name + section if available)  
- Practical next step for citizen
- Source documents used
"""),
            ("human", """Question: {question}

Legal Document Excerpts:
{context}

Provide a clear, grounded answer:""")
        ])

        try:
            langfuse_handler = CallbackHandler()
            chain = answer_prompt | self.llm
            response = chain.invoke({
                "question": question,
                "context": context
            }, config={"callbacks": [langfuse_handler]})

            content = response.content
            if isinstance(content, list):
                content = content[0].get("text", "") if len(content) > 0 else str(content)

            sources = list(set([c["source"] for c in chunks]))

            return {
                "answer": str(content),
                "sources": sources,
                "confidence": confidence,
                "grounded": True,
                "chunks_used": len(chunks),
                "chunks": chunks,
                "context": context
            }

        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return {
                "answer": "Unable to generate answer. Please try again.",
                "sources": [],
                "confidence": "error",
                "grounded": False
            }


_rag_instance = None

def get_rag() -> LegalRAGPipeline:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = LegalRAGPipeline()
    return _rag_instance