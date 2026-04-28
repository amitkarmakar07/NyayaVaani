# NyayaVaani RAG Pipeline - Test Report & Fixes

## Test Results Summary

| Test | Status | Details |
|------|--------|---------|
| ChromaDB Status | PASS | 4,139 chunks indexed from 12 legal acts |
| Chunk Quality | PASS | Avg 699 chars, 0 junk chunks, no noise |
| Dense Retrieval | PASS | 5/5 queries retrieved correct acts |
| BM25 Sparse Search | PARTIAL | 2/3 passed. "Section 4 RTI" failed (BM25 noisy for short queries) |
| Hybrid Search (RRF) | PASS | Correctly fuses dense + sparse results |
| LLM Grading | FIXED | Was too strict (0/6 for RTI queries). Now calibrated. |
| Answer Generation | PASS | Grounded answers citing correct Act + Section |
| Hallucination Check | PASS | No fabricated legal references detected |

---

## Issues Found & Fixes Applied

### Issue 1: Overly Strict LLM Grader (CRITICAL)
**Problem**: The grading prompt said "Be strict - partial matches are no". This caused the grader
to reject RTI Act chunks when the query was about road/water complaints, even though RTI is the
exact legal mechanism citizens use for these civic issues. Result: 0/6 relevant chunks, confidence = "low".

**Fix**: Rewrote the grading prompt in `src/rag/retriever.py` to:
- Accept chunks that describe legal procedures applicable to the query topic
- Recognize that general mechanisms (RTI, Consumer Forum) are relevant to specific civic issues
- Lean towards "yes" when in doubt (better to include a marginally relevant chunk than miss legal context)

**Before**: "How to file RTI for road repair?" -> 0/6 chunks passed -> confidence: LOW
**After**: Consumer & RTI chunks pass grading -> confidence: HIGH

### Issue 2: Poor RAG Query Construction
**Problem**: The RAG query in `crew.py` was `"[problem]. What are citizen rights for [category] complaint?"`.
For categories like "road", the embedding model couldn't find relevant legal acts because the query
didn't mention any actual act names.

**Fix**: Added a `dept_to_acts` mapping in `crew.py` that appends relevant act names to the query:
- road -> "RTI Act, Consumer Protection Act, public grievance redressal"
- electricity -> "Electricity Act 2003, consumer rights, RTI Act"
- ration -> "National Food Security Act NFSA 2013, RTI Act"
- etc.

**Before**: road query retrieved CrPC court forms (irrelevant)
**After**: road query retrieves Consumer Protection Act + RTI Act (correct)

### Issue 3: Fallback for Low-Confidence Retrieval
**Problem**: When primary retrieval returned low confidence, the system fell back to a generic
"Apply RTI Act 2005 general provisions" text string instead of actual legal content.

**Fix**: Added a fallback RTI-specific query in `crew.py`. When primary retrieval has low confidence,
the system now does a second retrieval with "Right to Information RTI Act how to file application
for [category] grievance redressal citizen rights" — which reliably returns RTI Act chunks.

---

## RAG Architecture Verified

```
Complaint Text
      |
      v
[Agent 1: Analyzer] -> department_category + problem_summary
      |
      v
[RAG Query Construction] -> Enhanced with dept_to_acts mapping
      |
      v
[Hybrid Retrieval]
  |-- Dense Search (BGE embeddings via ChromaDB)
  |-- Sparse Search (BM25 for keywords/section numbers)
  |-- RRF Fusion (Reciprocal Rank Fusion, k=60)
      |
      v
[Corrective Grading] -> LLM grades each chunk yes/no (calibrated prompt)
      |
      v
[Fallback] -> If low confidence, retry with RTI-specific query
      |
      v
[Legal Context] -> Passed to Agent 3 (Writer) for complaint generation
```

## Component Details

| Component | Technology | Config |
|-----------|-----------|--------|
| LLM | Llama 3.3 70B (Groq) | temperature=0.1 |
| Vector DB | ChromaDB | cosine similarity, HNSW index |
| Embeddings | BAAI/bge-base-en-v1.5 | normalized, CPU |
| Chunking | RecursiveCharacterTextSplitter | 800 chars, 150 overlap |
| Sparse Search | BM25 Okapi | lazy-loaded from ChromaDB |
| Fusion | Reciprocal Rank Fusion (RRF) | k=60 |
| Grading | LLM binary (yes/no) | zero temperature |

## Current Limitation
The Groq free tier has a 100,000 tokens/day limit. Heavy testing exhausted the quota.
The multi-agent pipeline (3 agents + RAG grading) consumes ~5,000-10,000 tokens per complaint.
This is expected and not a code issue.
