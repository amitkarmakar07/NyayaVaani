"""
Corrective RAG Retriever — Industry-grade retrieval pipeline
Uses Hybrid Search (Dense + BM25 Sparse) + Self-correction
Prevents hallucination via relevance scoring + source grounding
"""

from typing import List, Dict, Optional, Tuple
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.schema import Document
from rank_bm25 import BM25Okapi
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate

from config import config


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
            # ChromaDB metadata filter if department known
            # (skipped here as departments stored as JSON string)

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
            # Lazy load all docs for BM25
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

        # RRF scoring
        rrf_scores: Dict[str, float] = {}
        doc_map: Dict[str, Document] = {}
        rrf_k = 60  # standard RRF constant

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


class CorrectiveRAG:
    """
    Corrective RAG pipeline.
    1. Retrieve candidates
    2. Grade relevance of each chunk
    3. Filter out irrelevant chunks (prevents hallucination)
    4. If too few relevant chunks → web fallback with disclaimer
    5. Generate grounded answer
    """

    def __init__(self):
        self.retriever = HybridRetriever()
        self.llm = ChatGoogleGenerativeAI(
            model=config.LLM_MODEL,
            google_api_key=config.GOOGLE_API_KEY,
            temperature=0.0  # zero temp for grading — strict factual
        )
        logger.info("CorrectiveRAG initialized")

    def _grade_chunk_relevance(self, query: str, chunk: str) -> bool:
        """
        LLM grades if chunk is relevant to query.
        Binary yes/no -- filters hallucination sources.
        """
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a relevance grader for Indian legal documents used in a citizen grievance system.
Your job: decide if a document chunk contains information that could help answer the citizen's query.

Rules:
- Answer ONLY with "yes" or "no"
- "yes" = chunk contains legal rights, procedures, penalties, or remedies related to the query topic
- "yes" = chunk defines relevant legal terms, complaint filing procedures, or citizen entitlements applicable to the query
- "no" = chunk is clearly about a completely different legal topic with no connection
- When the query is about a civic issue (road, water, electricity etc.) and the chunk describes a general legal mechanism (like RTI, consumer forum, grievance redressal), mark as "yes" because citizens use these mechanisms for civic complaints
- When in doubt, lean towards "yes" -- it is better to include a marginally relevant chunk than to miss important legal context
"""),
            ("human", "Query: {query}\n\nChunk:\n{chunk}\n\nIs this chunk relevant or useful for answering the query? (yes/no):")
        ])

        try:
            chain = prompt | self.llm
            result = chain.invoke({"query": query, "chunk": chunk})
            return result.content.strip().lower().startswith("yes")
        except Exception as e:
            logger.warning(f"Grading failed: {e}, defaulting to True")
            return True

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=6))
    def retrieve_and_grade(
        self,
        query: str,
        department: Optional[str] = None
    ) -> Dict:
        """
        Full corrective RAG pipeline.
        Returns graded relevant chunks + confidence.
        """
        logger.info(f"RAG query: {query[:80]}...")

        # Step 1: Hybrid retrieval
        candidates = self.retriever.hybrid_search(query, k=config.TOP_K_RETRIEVAL)
        logger.info(f"Retrieved {len(candidates)} candidate chunks")

        # Step 2: Grade each chunk
        relevant_chunks = []
        for doc, score in candidates:
            is_relevant = self._grade_chunk_relevance(query, doc.page_content)
            if is_relevant:
                relevant_chunks.append({
                    "content": doc.page_content,
                    "source": doc.metadata.get("act_name", "Unknown Act"),
                    "page": doc.metadata.get("page_number", "N/A"),
                    "score": round(score, 3)
                })

        logger.info(f"Relevant chunks after grading: {len(relevant_chunks)}/{len(candidates)}")

        # Step 3: Determine confidence
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

    def answer_question(self, question: str, department: Optional[str] = None) -> Dict:
        """
        Full RAG answer generation with anti-hallucination.
        Used by: RAG Chatbot tab in frontend.
        """
        retrieval = self.retrieve_and_grade(question, department)
        chunks = retrieval["chunks"]
        confidence = retrieval["confidence"]

        if confidence == "low":
            return {
                "answer": (
                    "I could not find specific information about this in the available "
                    "legal documents. Please consult pgportal.gov.in or a legal advisor "
                    "for accurate guidance on this matter."
                ),
                "sources": [],
                "confidence": "low",
                "grounded": False
            }

        # Build context string
        context = ""
        for i, chunk in enumerate(chunks):
            context += f"\n--- Source {i+1}: {chunk['source']} (Page {chunk['page']}) ---\n"
            context += chunk["content"] + "\n"

        # Answer prompt
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
            chain = answer_prompt | self.llm
            response = chain.invoke({
                "question": question,
                "context": context
            })

            sources = list(set([c["source"] for c in chunks]))

            return {
                "answer": response.content,
                "sources": sources,
                "confidence": confidence,
                "grounded": True,
                "chunks_used": len(chunks)
            }

        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return {
                "answer": "Unable to generate answer. Please try again.",
                "sources": [],
                "confidence": "error",
                "grounded": False
            }


# Singleton instance
_rag_instance = None

def get_rag() -> CorrectiveRAG:
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = CorrectiveRAG()
    return _rag_instance