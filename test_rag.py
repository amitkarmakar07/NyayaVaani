"""
RAG Module End-to-End Test Script
Tests: ChromaDB status, chunking quality, retrieval, grading, hallucination detection
"""

import json
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

print("=" * 70)
print("  NyayaVaani RAG Module -- Comprehensive Test")
print("=" * 70)

# ─── TEST 1: ChromaDB Collection Status ─────────────────────────────
print("\n\n[TEST 1] ChromaDB Collection Status")
print("-" * 50)

embeddings = HuggingFaceEmbeddings(
    model_name=config.EMBEDDING_MODEL,
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True}
)
vectorstore = Chroma(
    persist_directory=config.CHROMA_DIR,
    embedding_function=embeddings,
    collection_name="nyayavaani_acts"
)

collection = vectorstore._collection
total_chunks = collection.count()
print(f"  Total chunks in ChromaDB: {total_chunks}")

if total_chunks == 0:
    print("  [FAIL] ChromaDB is EMPTY! Need to re-index.")
    sys.exit(1)
else:
    print(f"  [PASS] ChromaDB has {total_chunks} chunks indexed.")

# ─── TEST 2: Chunk Quality Analysis ─────────────────────────────────
print("\n\n[TEST 2] Chunk Quality Analysis")
print("-" * 50)

all_data = collection.get(include=["documents", "metadatas"])
documents = all_data["documents"]
metadatas = all_data["metadatas"]

# Chunk length statistics
lengths = [len(doc) for doc in documents]
avg_len = sum(lengths) / len(lengths) if lengths else 0
min_len = min(lengths) if lengths else 0
max_len = max(lengths) if lengths else 0

print(f"  Avg chunk length: {avg_len:.0f} chars")
print(f"  Min chunk length: {min_len} chars")
print(f"  Max chunk length: {max_len} chars")
print(f"  Config chunk_size: {config.CHUNK_SIZE} chars")
print(f"  Config chunk_overlap: {config.CHUNK_OVERLAP} chars")

# Count very short chunks (potential noise)
short_chunks = sum(1 for l in lengths if l < 100)
very_short = sum(1 for l in lengths if l < 50)
print(f"  Chunks < 100 chars (noise): {short_chunks} ({short_chunks/len(lengths)*100:.1f}%)")
print(f"  Chunks < 50 chars  (junk):  {very_short} ({very_short/len(lengths)*100:.1f}%)")

if short_chunks / len(lengths) > 0.15:
    print("  [WARN] High ratio of short chunks -- may hurt retrieval quality.")
else:
    print("  [PASS] Chunk sizes look healthy.")

# Count documents per source act
act_counts = {}
for meta in metadatas:
    act = meta.get("act_name", "Unknown")
    act_counts[act] = act_counts.get(act, 0) + 1

print(f"\n  Chunks per Act:")
for act, count in sorted(act_counts.items()):
    print(f"    {act}: {count} chunks")

# ─── TEST 3: Dense Retrieval (Semantic Search) ──────────────────────
print("\n\n[TEST 3] Dense Retrieval -- Semantic Search")
print("-" * 50)

test_queries = [
    {
        "query": "What are the rights of electricity consumers under Indian law?",
        "expected_acts": ["Electricity Act 2003"],
        "category": "electricity"
    },
    {
        "query": "How to file an RTI application and what is the fee?",
        "expected_acts": ["RTI Act 2005"],
        "category": "rti"
    },
    {
        "query": "What are the penalties for corruption by a public servant?",
        "expected_acts": ["Prevention of Corruption Act 1988", "Lokpal Act 2013"],
        "category": "corruption"
    },
    {
        "query": "What is the process to file a consumer complaint in consumer forum?",
        "expected_acts": ["Consumer Protection Act 2019", "Consumer Forum Filing Guide"],
        "category": "consumer"
    },
    {
        "query": "What are the rights of children to free education?",
        "expected_acts": ["RTE Act 2009"],
        "category": "education"
    },
]

retrieval_results = []

for i, tq in enumerate(test_queries, 1):
    results = vectorstore.similarity_search_with_relevance_scores(tq["query"], k=6)
    
    print(f"\n  Query {i}: \"{tq['query'][:60]}...\"")
    print(f"  Expected: {tq['expected_acts']}")
    
    found_acts = set()
    for doc, score in results:
        act = doc.metadata.get("act_name", "Unknown")
        page = doc.metadata.get("page_number", "?")
        found_acts.add(act)
        print(f"    -> [{score:.3f}] {act} (Page {page}) | {doc.page_content[:80]}...")
    
    # Check if expected act was retrieved
    expected_found = any(
        any(exp.lower() in act.lower() for act in found_acts)
        for exp in tq["expected_acts"]
    )
    
    if expected_found:
        print(f"  [PASS] Expected act found in top-6 results!")
    else:
        print(f"  [FAIL] Expected act NOT found. Got: {found_acts}")
    
    retrieval_results.append({
        "query": tq["query"],
        "expected": tq["expected_acts"],
        "found": list(found_acts),
        "passed": expected_found,
        "top_score": results[0][1] if results else 0
    })

pass_count = sum(1 for r in retrieval_results if r["passed"])
print(f"\n  Retrieval Accuracy: {pass_count}/{len(retrieval_results)} queries passed")

# ─── TEST 4: BM25 Sparse Search ─────────────────────────────────────
print("\n\n[TEST 4] BM25 Sparse Search (Keyword Matching)")
print("-" * 50)

from src.rag.retriever import HybridRetriever

hybrid = HybridRetriever()

bm25_queries = [
    ("Section 4 RTI Act", "RTI"),
    ("Section 126 Electricity Act", "Electricity"),
    ("Section 35 Consumer Protection", "Consumer"),
]

for query, expected_keyword in bm25_queries:
    sparse_results = hybrid.sparse_search(query, k=3)
    print(f"\n  Query: \"{query}\"")
    for doc in sparse_results:
        act = doc.metadata.get("act_name", "Unknown")
        print(f"    -> {act} | {doc.page_content[:80]}...")
    
    found = any(expected_keyword.lower() in doc.metadata.get("act_name", "").lower() for doc in sparse_results)
    print(f"  {'[PASS]' if found else '[FAIL]'} {'Found' if found else 'Missing'} {expected_keyword} in results")

# ─── TEST 5: Hybrid Search (RRF Fusion) ─────────────────────────────
print("\n\n[TEST 5] Hybrid Search (Dense + Sparse RRF Fusion)")
print("-" * 50)

hybrid_query = "What are citizen rights and legal remedies for electricity complaint in India?"
hybrid_results = hybrid.hybrid_search(hybrid_query, k=6)

print(f"  Query: \"{hybrid_query[:60]}...\"")
print(f"  Hybrid results: {len(hybrid_results)}")
for doc, score in hybrid_results:
    act = doc.metadata.get("act_name", "Unknown")
    page = doc.metadata.get("page_number", "?")
    print(f"    -> [RRF: {score:.4f}] {act} (Page {page}) | {doc.page_content[:80]}...")

# ─── TEST 6: Corrective RAG Grading ─────────────────────────────────
print("\n\n[TEST 6] Corrective RAG -- LLM Grading & Hallucination Filter")
print("-" * 50)

from src.rag.retriever import CorrectiveRAG

crag = CorrectiveRAG()

grading_tests = [
    {
        "query": "What are consumer rights when buying products online?",
        "department": "consumer",
        "description": "Consumer Protection (should find chunks)"
    },
    {
        "query": "How to file RTI for road repair in my area?",
        "department": "road",
        "description": "RTI for civic issue (should find chunks)"
    },
    {
        "query": "What is the punishment for bribery by government officials?",
        "department": "corruption",
        "description": "Anti-corruption law (should find chunks)"
    },
]

for test in grading_tests:
    print(f"\n  [{test['description']}]")
    print(f"  Query: \"{test['query']}\"")
    
    result = crag.retrieve_and_grade(test["query"], department=test["department"])
    
    print(f"  Total Retrieved: {result['total_retrieved']}")
    print(f"  Relevant (after grading): {result['total_relevant']}")
    print(f"  Confidence: {result['confidence']}")
    
    if result["chunks"]:
        for chunk in result["chunks"]:
            print(f"    -> [{chunk['score']:.3f}] {chunk['source']} (Page {chunk['page']})")
            print(f"      Content: {chunk['content'][:100]}...")
    else:
        print(f"  [WARN] NO chunks passed grading! Grader may be too strict.")
    
    if result["confidence"] == "low" and result["total_retrieved"] > 0:
        print(f"  [ISSUE] Retrieved {result['total_retrieved']} chunks but NONE passed grading.")
        print(f"          -> LLM grader may be TOO STRICT. This causes the pipeline to lose legal context.")

# ─── TEST 7: Full RAG Answer Generation ─────────────────────────────
print("\n\n[TEST 7] Full RAG Answer Generation (Hallucination Check)")
print("-" * 50)

answer_test = crag.answer_question(
    "What are the rights of consumers when they receive a defective product?",
    department="consumer"
)

print(f"  Confidence: {answer_test['confidence']}")
print(f"  Grounded: {answer_test['grounded']}")
print(f"  Sources: {answer_test['sources']}")
print(f"  Answer preview: {answer_test['answer'][:300]}...")

if answer_test["grounded"]:
    print(f"  [PASS] Answer is grounded in source documents.")
else:
    print(f"  [WARN] Answer is NOT grounded — returned fallback response.")

# ─── SUMMARY ────────────────────────────────────────────────────────
print("\n\n" + "=" * 70)
print("  RAG MODULE TEST SUMMARY")
print("=" * 70)
print(f"  ChromaDB chunks:      {total_chunks}")
print(f"  Source acts indexed:   {len(act_counts)}")
print(f"  Avg chunk size:        {avg_len:.0f} chars")
print(f"  Short chunks (<100):   {short_chunks}")
print(f"  Retrieval accuracy:    {pass_count}/{len(retrieval_results)}")
print(f"  Answer grounded:       {answer_test['grounded']}")
print("=" * 70)
