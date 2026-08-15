<div align="center">

# ⚖️ NyayaVaani: Agentic AI Civic Assistant & Legal RAG Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![CrewAI](https://img.shields.io/badge/CrewAI-Multi--Agent-red?logo=ai&logoColor=white)](https://www.crewai.com/)
[![Gemini](https://img.shields.io/badge/Google%20Gemini-2.5%20Flash-orange?logo=google&logoColor=white)](https://deepmind.google/technologies/gemini/)
[![Whisper](https://img.shields.io/badge/OpenAI%20Whisper-V3-black?logo=openai&logoColor=white)](https://openai.com/research/whisper)
[![Langfuse](https://img.shields.io/badge/Langfuse-Observability-purple?logo=analytics&logoColor=white)](https://langfuse.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**NyayaVaani** (Voice of Justice) is an enterprise-grade, multimodal AI platform designed to empower Indian citizens in civic grievance redressal and legal awareness. It integrates a **5-Agent Autonomous CrewAI Workflow**, a **Hybrid Legal RAG Pipeline (Dense + Sparse + Reranker)**, **NeMo-inspired Security Guardrails**, and **OpenTelemetry/Langfuse Observability**.

[Explore Architecture](#-system-architecture--observability-mesh) • [Tech Stack](#-technology-stack--model-topology) • [Security & Metrics](#-security-guardrails--observability-metrics) • [Quickstart](#-installation--setup)

</div>

---

## 🌟 System Overview

Filing civic complaints in India often involves navigational friction, unclear department jurisdictions, and complex legal formatting. **NyayaVaani** solves this through two core engines:

### 🤖 1. CrewAI Multi-Agent Pipeline (Sequential Workflow)
Processes raw citizen complaints (text or voice) through 5 specialized autonomous agents operating in sequence:
1. **Grievance Analyst Agent**: Extracts problem category (electricity, water, road, consumer, police), severity rating, prior complaints, and citizen impact (`AnalyzerOutput`).
2. **Department Scout Agent**: Executes real-time web & database lookups (`department_lookup_tool`, `state_helpline_tool`) to resolve central/state nodal authorities and official helplines (`site:gov.in`).
3. **Legal Researcher Agent**: Invokes `legal_rag_tool` to search statutory Indian acts, sections, and constitutional rights.
4. **Document Architect Agent**: Drafts legally grounded, professionally formatted Complaint Letters, RTI Applications, Emails, and SMS alerts (`WriterOutput`).
5. **Social Media Scout Agent**: Resolves official Twitter/X handles (`twitter_handle_lookup_tool`) and drafts targeted public escalation tweets (`SocialMediaOutput`).

### 📚 2. Hybrid Legal RAG Pipeline (Statutory Assistant)
Enables interactive legal Q&A over Indian Acts (Consumer Protection Act, RTI Act, Electricity Act, Municipal Acts) with strict zero-hallucination guarantees:
- **Hybrid Retrieval**: Combines Dense Semantic Search (`BAAI/bge-m3` via ChromaDB) with Sparse Keyword Match (`BM25Okapi`) via Reciprocal Rank Fusion (RRF).
- **Cross-Encoder Reranking**: Re-scores candidate chunks using `BAAI/bge-reranker-base` (`ms-marco-MiniLM-L-6-v2`).
- **Confidence Scoring**: Evaluates chunk relevance (`HIGH`, `MEDIUM`, `LOW`) to output explicit safety warnings on low context match.
- **Strict Grounding**: Instructs LLM to answer *only* from retrieved excerpts with mandatory statutory section citations.

---

## 🛠️ Technology Stack & Model Topology

| Layer | Framework / Component | Details & Models Used |
| :--- | :--- | :--- |
| **Backend Framework** | FastAPI, Uvicorn, Python 3.10+ | Async REST API, Streaming responses, Background Tasks |
| **Agent Orchestration** | CrewAI, LangChain | Sequential Process DAG, Pydantic Structured Outputs |
| **Generative LLMs** | Google Gemini 2.5 Flash / GPT-4o-mini | Core agent reasoning & response generation (`temperature=0.3`) |
| **Security Guardrails** | NeMo Guardrails + `gpt-4o-mini` | Layer 1: Regex PII/Jailbreak Filter (<1ms) <br> Layer 2: Fast LLM Evaluator (~250ms) |
| **Speech-to-Text (STT)** | OpenAI Whisper (v3) | Audio transcription (Hindi, English, Hinglish code-switching) |
| **Embeddings & Vector DB** | HuggingFace `BAAI/bge-m3` + ChromaDB | Dense vector similarity search (768d normalized) |
| **Sparse Keyword Search** | Rank-BM25 (`BM25Okapi`) | Exact statutory act & section number matching |
| **Reranker Model** | Cross-Encoder (`ms-marco-MiniLM-L-6-v2`) | Deep query-document pair re-scoring |
| **LLM-as-a-Judge** | Langfuse Evaluator Engine | Faithfulness, Answer Relevance, and Hallucination scoring |
| **Observability** | Langfuse + OpenTelemetry | OTLP Collector (`CrewAIInstrumentor` + `LiteLLMInstrumentor`) |

---

## 🏗️ System Architecture & Observability Mesh

### 🤖 1. CrewAI Multi-Agent Architecture
![CrewAI Multi-Agent Architecture](./assets/crew_architecture.png)

---

### 📚 2. Hybrid Legal RAG Pipeline Architecture
![Hybrid Legal RAG Architecture](./assets/rag_architecture.png)

---

## 🛡️ Security Guardrails & Observability Metrics

### 🛡️ Multi-Layer Security Shield
- **Layer 1: Instant Regex Pre-Filter (<1ms)**: Scans for sensitive Indian PII (Aadhaar `[2-9]\d{3}\d{4}\d{4}`, PAN `[A-Z]{5}[0-9]{4}[A-Z]`, Phone, Email) and system prompt injection patterns.
- **Layer 2: Fast LLM Security Evaluator (~250ms)**: 1-token structured `gpt-4o-mini` classifier filtering off-topic queries while permitting greetings, follow-up questions, and informal typo phrasing.
- **NeMo Guardrails Integration**: Off-Topic, PII, and Jailbreak detection policies.
- **Output Shield**: Content toxicity and policy violation guardrails.

### 📊 Observability (Langfuse + OpenTelemetry)
Every request is instrumented with OpenTelemetry (`OTLPSpanExporter`), tracking **5 Core Pillars**:
1. **Evaluations**: LLM-as-a-Judge scoring.
2. **Cost**: Model-wise API expenditure and token pricing.
3. **Tokens**: Prompt vs completion tokens.
4. **Latency**: Per-step agent execution & end-to-end request latencies.
5. **Logs & Traces**: Hierarchical parent-child span trees for agent tool calls and LLM invocations.

### 🎯 LLM-as-a-Judge Benchmark Metrics
Evaluated across golden dataset test suites (`eval/RAG_Golden_Dataset.csv`):

| Evaluation Metric | Score |
| :--- | :---: |
| **Faithfulness Score** | **0.92** |
| **Answer Relevance Score** | **0.89** |
| **Context Precision & Recall** | **0.91** |
| **RAG Query Response Latency** | **5-6s** |

---

## 📦 Installation & Setup

1. **Clone the Repository**
   ```bash
   git clone https://github.com/amitkarmakar07/NyayaVaani.git
   cd NyayaVaani
   ```

2. **Configure Environment Variables**
   Create a `.env` file in the root directory:
   ```env
   GOOGLE_API_KEY=your_gemini_api_key
   OPENAI_API_KEY=your_openai_api_key
   SERPAPI_API_KEY=your_serpapi_key
   LANGFUSE_PUBLIC_KEY=your_langfuse_pk
   LANGFUSE_SECRET_KEY=your_langfuse_sk
   LANGFUSE_HOST=http://127.0.0.1:3000
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch Application Server**
   ```bash
   python -m backend.api
   ```
   Open `http://localhost:8000/frontend/index.html` in your web browser.

---

## ⚖️ License
Distributed under the MIT License. See `LICENSE` for more information.

---

## 👨‍💻 Author
**Amit Karmakar**  
*Data Science & AI Developer*  
[LinkedIn](https://www.linkedin.com/in/amit-karmakar-355817258/) • [GitHub](https://github.com/amitkarmakar07)
